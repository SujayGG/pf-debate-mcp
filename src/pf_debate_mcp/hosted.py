"""The free public server: `pf-debate-mcp serve-http`, reached through Cloudflare (see docs/hosting.md).

Everything hosted-specific is switched on here, once, at startup:
  - stateless streamable HTTP (no MCP sessions: nothing to expire, any restart is harmless)
  - Host-header allow-list (the SDK otherwise only accepts "localhost")
  - store keeps cuts in memory under random ids; exports are 1-hour download links
  - SSRF guard on fetch_source; per-tool daily budgets; one JSON log line per call
  - caselist tools (need each student's own Tabroom login) and build_library are not offered

  Claude / Gemini / ChatGPT ──▶ Cloudflare Worker ──▶ this app (/mcp, /health, /stats, /files/…)
"""

import json
import os
import sys
import threading
import time
from collections import defaultdict

from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import library, llm, metrics, semantic, server, store
from .server import mcp

LOCAL_ONLY_TOOLS = ("caselist_search", "caselist_team", "caselist_download", "build_library")
STARTED = time.time()
LIMITS = {"default": 120, "llm": 20}  # requests per minute per client IP for the web app's /api/*
_hits: dict[tuple[str, str], list[float]] = defaultdict(list)
_hits_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    # The Worker forwards the student's real IP; web-app traffic (unlike connectors) comes from students.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")


def _allow(request: Request, bucket: str) -> bool:
    key, now = (_client_ip(request), bucket), time.time()
    with _hits_lock:
        recent = [t for t in _hits[key] if now - t < 60]
        if len(recent) >= LIMITS[bucket]:
            _hits[key] = recent
            return False
        _hits[key] = recent + [now]
        if len(_hits) > 50_000:  # keep the table bounded
            _hits.clear()
        return True


def _error(e: Exception) -> JSONResponse:
    msg = str(e)
    status = 422 if "REJECTED" in msg else 404 if ("not found" in msg or "expired" in msg) else \
        429 if "limit" in msg else 400
    return JSONResponse({"error": msg}, status_code=status)


def _api(bucket: str = "default"):
    """Wrap a sync handler: per-IP rate limit, run in a thread, ToolError/ValueError -> JSON error."""
    def deco(fn):
        async def handler(request: Request) -> Response:
            if not _allow(request, bucket):
                return JSONResponse({"error": "Too many requests from your network. Wait a minute."}, 429)
            try:
                body = await request.json() if request.method == "POST" else {}
            except json.JSONDecodeError:
                return JSONResponse({"error": "Send a JSON body."}, 400)
            try:
                result = await run_in_threadpool(fn, request, body)
            except (ToolError, ValueError, TypeError) as e:  # TypeError: wrong field types from the client
                return _error(e)
            except llm.PoolExhausted as e:
                return JSONResponse({"error": str(e), "exhausted": True}, 429)
            return result if isinstance(result, Response) else JSONResponse(result)
        return handler
    return deco


def _card_json(card: dict) -> dict:
    return {k: card.get(k) for k in ("id", "tag", "cite_short", "cite_rest", "times_read", "origin")} | \
        {"runs": [list(r) for r in card["runs"]]}


def _openai_tools(tools) -> list[dict]:
    return [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                              "parameters": t.input_schema}} for t in tools]


def _register_api() -> None:
    q = lambda r, k, d=None: r.query_params.get(k) or d  # noqa: E731

    @mcp.custom_route("/api/search", methods=["GET"])
    @_api()
    def search(r, _):
        year = q(r, "year_from")
        return {"results": server.search_cards(q(r, "q", ""), "library", int(year) if year else None,
                                                q(r, "side"), q(r, "event"), q(r, "sort", "relevance"),
                                                int(q(r, "limit", 10)), q(r, "mode", "hybrid"))}

    @mcp.custom_route("/api/card/{card_id}", methods=["GET"])
    @_api()
    def card(r, _):
        return _card_json(server._card(r.path_params["card_id"]))

    @mcp.custom_route("/api/find", methods=["GET"])
    @_api()
    def find(r, _):
        kinds = [k for k in q(r, "kinds", "papers,news").split(",") if k]
        return server.find_sources(q(r, "q", ""), kinds, int(q(r, "limit", 10)))

    @mcp.custom_route("/api/fetch", methods=["POST"])
    @_api()
    def fetch(_, body):
        sid, src = server.resolve_source(str(body.get("url", "")))
        meta = {k: src.get(k) for k in ("url", "title", "author", "date", "publisher")}
        return {"source_id": sid, "meta": meta, "paragraphs": server.paragraphs(src["text"])}

    @mcp.custom_route("/api/suggest", methods=["POST"])
    @_api()
    def suggest(_, body):
        try:
            return semantic.suggest(server._source_text(str(body.get("source_id", ""))), str(body.get("claim", "")))
        except server.CutError as e:
            raise ToolError(f"Couldn't suggest a cut: {e}") from None

    @mcp.custom_route("/api/cut", methods=["POST"])
    @_api()
    def cut(_, body):
        fields = ("source_id", "tag", "author", "date", "title", "publisher", "url", "quals", "start_quote",
                  "end_quote", "highlight", "underline", "paragraph")
        card, warnings = server.make_card(**{k: body.get(k) for k in fields if k in body})
        return {"card": _card_json(card), "warnings": warnings}

    @mcp.custom_route("/api/export", methods=["POST"])
    @_api()
    def export(_, body):
        name, data = server.render_doc(str(body.get("title", "pf-doc")), body.get("items", []), None,
                                       body.get("format", "docx"))
        safe = "".join(c if c.isalnum() or c in "._-" else "-" for c in name)
        kind = "text/html" if safe.endswith(".html") else \
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return Response(data, media_type=kind, headers={"Content-Disposition": f'attachment; filename="{safe}"'})

    @mcp.custom_route("/api/tools", methods=["GET"])
    async def tools(_: Request) -> Response:
        return JSONResponse({"tools": _openai_tools(await mcp.list_tools())})

    @mcp.custom_route("/api/tool/{name}", methods=["POST"])
    async def tool(request: Request) -> Response:
        if not _allow(request, "default"):
            return JSONResponse({"error": "Too many requests from your network. Wait a minute."}, 429)
        try:
            args = (await request.json()).get("arguments") or {}
            result = await mcp.call_tool(request.path_params["name"], args)
        except ToolError as e:
            return JSONResponse({"content": str(e), "is_error": True})
        except Exception as e:  # a crash inside a tool: report it to the model without internals
            if isinstance(e, (json.JSONDecodeError, AttributeError)):
                return JSONResponse({"error": "Send {\"arguments\": {...}}."}, 400)
            return JSONResponse({"content": f"The tool failed ({type(e).__name__}). Try again or rephrase.",
                                 "is_error": True})
        text = "\n".join(getattr(b, "text", "") for b in result.content)
        return JSONResponse({"content": text, "is_error": bool(result.is_error)})

    @mcp.custom_route("/api/system", methods=["GET"])
    async def system(_: Request) -> Response:
        guide = server.pf_guide("pf-debate")
        return JSONResponse({"prompt": server.INSTRUCTIONS + "\n\n" + guide +
                             "\n\nYou are running inside the pf-debate web app; call the tools directly."})

    @mcp.custom_route("/api/llm", methods=["POST"])
    @_api("llm")
    def chat(_, body):
        return llm.chat(body.get("messages", []), body.get("tools"))

    @mcp.custom_route("/api/llm/status", methods=["GET"])
    async def llm_status(_: Request) -> Response:
        return JSONResponse(llm.status())


def configure(public_url: str, allowed_hosts: list[str]):
    """Switch the process into hosted mode and return the ASGI app."""
    store.enable_hosted(public_url)
    metrics.ENABLED = True
    for name in LOCAL_ONLY_TOOLS:
        mcp.remove_tool(name)
    _register_api()

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> Response:
        ready = library.ready()
        return JSONResponse({"ok": ready, "library": library.db_path().name if ready else None,
                             "uptime_s": round(time.time() - STARTED)}, status_code=200 if ready else 503)

    @mcp.custom_route("/stats", methods=["GET"])
    async def stats(_: Request) -> Response:
        return JSONResponse(metrics.stats())

    @mcp.custom_route("/files/{token}/{name}", methods=["GET"])
    async def files(request: Request) -> Response:
        hit = store.get_export(request.path_params["token"])
        if not hit:
            return Response("This download link expired (links last 1 hour). Export again.", status_code=404)
        filename, data = hit
        kind = "text/html" if filename.endswith(".html") else \
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return Response(data, media_type=kind, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    security = TransportSecuritySettings(
        allowed_hosts=allowed_hosts + ["127.0.0.1:*", "localhost:*"],  # localhost: container health checks
        allowed_origins=[f"https://{h}" for h in allowed_hosts])
    return mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=security,
                                   host="0.0.0.0")


def serve(host: str, port: int, public_url: str, allowed_hosts: list[str]) -> None:
    import uvicorn

    if int(os.environ.get("WEB_CONCURRENCY", "1")) > 1:
        sys.exit("Hosted mode keeps cuts in memory, so it must run as ONE process (unset WEB_CONCURRENCY). "
                 "Threads already serve many students at once.")
    if not library.ready():
        library.download(log=lambda m: print(m, file=sys.stderr, flush=True))
    semantic._loaded()  # starts building the plain-English search index in the background if missing
    app = configure(public_url, allowed_hosts)
    uvicorn.run(app, host=host, port=port, workers=1, proxy_headers=True, forwarded_allow_ips="*")
