"""The free public server: `pf-debate-mcp serve-http` (run on a Hugging Face Space behind Cloudflare).

Everything hosted-specific is switched on here, once, at startup:
  - stateless streamable HTTP (no MCP sessions: nothing to expire, any restart is harmless)
  - Host-header allow-list (the SDK otherwise only accepts "localhost")
  - store keeps cuts in memory under random ids; exports are 1-hour download links
  - SSRF guard on fetch_source; per-tool daily budgets; one JSON log line per call
  - caselist tools (need each student's own Tabroom login) and build_library are not offered

  Claude / Gemini / ChatGPT ──▶ Cloudflare Worker ──▶ this app (/mcp, /health, /stats, /files/…)
"""

import os
import sys
import time

from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import library, metrics, store
from .server import mcp

LOCAL_ONLY_TOOLS = ("caselist_search", "caselist_team", "caselist_download", "build_library")
STARTED = time.time()


def configure(public_url: str, allowed_hosts: list[str]):
    """Switch the process into hosted mode and return the ASGI app."""
    store.enable_hosted(public_url)
    metrics.ENABLED = True
    for name in LOCAL_ONLY_TOOLS:
        mcp.remove_tool(name)

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
    app = configure(public_url, allowed_hosts)
    uvicorn.run(app, host=host, port=port, workers=1, proxy_headers=True, forwarded_allow_ips="*")
