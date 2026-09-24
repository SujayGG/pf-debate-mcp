"""Hosted-mode behavior: isolation, memory bounds, budgets, SSRF guard, upload caps, and a real
end-to-end run of `pf-debate-mcp serve-http` in a subprocess (so its global switches can't leak
into the other tests)."""

import asyncio
import io
import os
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from conftest import PAGES
from pf_debate_mcp import docx_io, metrics, sources, store


@pytest.fixture
def hosted_store(monkeypatch):
    monkeypatch.setattr(store, "HOSTED", True)
    monkeypatch.setattr(store, "PUBLIC_URL", "https://debate.test")
    monkeypatch.setattr(store, "_cards", store._ByteLRU(10_000))
    monkeypatch.setattr(store, "_sources", store._ByteLRU(10_000))


def test_hosted_ids_are_random_and_unguessable(hosted_store):
    a = store.add_card("t", "S 25", "[c]", "body text.", [(0, 4)], [(0, 4)], "x")
    b = store.add_card("t", "S 25", "[c]", "body text.", [(0, 4)], [(0, 4)], "x")
    assert a.startswith("c_") and len(a) == 14 and a != b
    assert store.get_card("c1") is None and store.get_card(a)["tag"] == "t"


def test_hosted_memory_is_bounded_by_bytes(hosted_store):
    first = store.add_source("http://a.test", {}, "x" * 6_000)
    store.add_source("http://b.test", {}, "y" * 6_000)  # 12 KB > 10 KB cap: the oldest is evicted
    assert store.get_source(first) is None


def test_hosted_export_is_a_download_link(hosted_store):
    link = store.save_export("case.docx", b"data")
    token = link.split("/files/")[1].split("/")[0]
    assert link.startswith("https://debate.test/files/") and store.get_export(token) == ("case.docx", b"data")


def test_daily_budget(monkeypatch):
    monkeypatch.setattr(metrics, "ENABLED", True)
    monkeypatch.setitem(metrics.BUDGETS, "pf_guide", 1)
    metrics.calls.clear()
    from pf_debate_mcp.server import pf_guide

    pf_guide("format")
    with pytest.raises(ToolError, match="today's limit"):
        pf_guide("format")
    metrics.calls.clear()


@pytest.fixture
def any_port(web, monkeypatch):  # the test web server runs on a random port
    monkeypatch.setattr(sources, "ALLOWED_PORTS", {None, 80, 443, int(web.rsplit(":", 1)[1])})


def test_ssrf_blocks_odd_ports():
    with pytest.raises(sources.FetchError, match="standard ports"):
        sources.check_public("https://example.com:8443/")


def test_ssrf_blocks_private_addresses(web, any_port):
    with pytest.raises(sources.FetchError, match="private or internal"):
        sources.fetch(f"{web}/article", block_private=True)


def test_ssrf_checks_every_redirect_hop(web, any_port, monkeypatch):
    port = web.rsplit(":", 1)[1]
    PAGES["/hop"] = ("redirect", f"http://localhost:{port}/article".encode())
    real = socket.getaddrinfo

    def fake(host, *args, **kw):  # pretend the first host is public so only the redirect target is private
        if host == "127.0.0.1":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
        return real(host, *args, **kw)

    monkeypatch.setattr(sources, "_resolve", fake)
    with pytest.raises(sources.FetchError, match="private or internal"):
        sources.fetch(f"{web}/hop", block_private=True)


def test_download_size_cap(web, monkeypatch):
    monkeypatch.setitem(sources.MAX_BYTES, False, 100)
    with pytest.raises(sources.FetchError, match="too large"):
        sources.fetch(f"{web}/article")


def test_docx_zip_bomb_rejected(monkeypatch, tmp_path):
    path = docx_io.export("x", [{"pocket": "p"}], tmp_path / "x.docx")
    monkeypatch.setattr(docx_io, "MAX_UNZIPPED", 1_000)
    with pytest.raises(ValueError, match="zip bomb"):
        docx_io.parse(path.read_bytes())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a", "b")
    with pytest.raises(ValueError, match="over 10 MB"):
        docx_io.parse(b"0" * (docx_io.MAX_DOCX + 1))


# --- end to end: the real hosted server in its own process ---------------------------------------

@pytest.fixture(scope="module")
def server(tiny_library, tmp_path_factory):
    home = Path(os.environ["PF_DEBATE_HOME"])  # has the tiny library
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "PF_DEBATE_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen([sys.executable, "-m", "pf_debate_mcp", "serve-http", "--port", str(port),
                             "--host", "127.0.0.1", "--public-url", f"http://127.0.0.1:{port}",
                             "--allowed-host", "debate.test"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("hosted server did not start:\n" + proc.stdout.read().decode(errors="replace")[-2000:])
    yield base
    proc.kill()


def _mcp_calls(base: str, calls: list[tuple[str, dict]]):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def run():
        async with streamable_http_client(f"{base}/mcp") as streams, ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            results = [await s.call_tool(name, args) for name, args in calls]
            return tools, results

    return asyncio.run(run())


def test_e2e_hosted_flow(server):
    tools, (search, recut, fetch_private) = _mcp_calls(server, [
        ("search_cards", {"query": "nuclear war"}),
        ("cut_card", {"source_id": "lib:1", "tag": "Econ decline raises war risk", "author": "Harris",
                      "date": "2009", "title": "t", "publisher": "p", "url": "http://x.test", "quals": "q",
                      "start_quote": "Context", "end_quote": "great power war",
                      "highlight": ["risk of great power war"]}),
        ("fetch_source", {"url_or_id": f"{server}/health"}),
    ])
    assert "caselist_search" not in tools and "build_library" not in tools and "cut_card" in tools
    assert "lib:1" in " ".join(c.text for c in search.content)  # list results: one block per item
    cid = recut.content[0].text.split("Saved as ")[1].split(".")[0]
    assert cid.startswith("c_") and not recut.is_error
    blocked = fetch_private.content[0].text  # local URL on a random port: either guard rule may fire first
    assert fetch_private.is_error and ("private or internal" in blocked or "standard ports" in blocked)

    _, (export,) = _mcp_calls(server, [("export_doc", {"title": "Neg", "items": [{"card": cid}]})])
    link = export.content[0].text.split(": ", 1)[1].split()[0]
    r = httpx.get(link)
    assert r.status_code == 200 and r.content[:2] == b"PK"  # a real .docx (zip)


def test_e2e_rejects_unknown_host_header(server):
    r = httpx.post(f"{server}/mcp", headers={"Host": "evil.test", "Content-Type": "application/json",
                                             "Accept": "application/json, text/event-stream"},
                   json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code in (400, 403, 421)


def test_e2e_stats_have_no_content(server):
    stats = httpx.get(f"{server}/stats").json()
    text = str(stats)
    assert "nuclear" not in text and "Harris" not in text  # counts only, never queries or card text
