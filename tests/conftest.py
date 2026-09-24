"""Shared fixtures. PF_DEBATE_HOME is pointed at a temp dir before any pf_debate_mcp import,
so tests never touch the real ~/.pf-debate library or the user's cards."""

import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["PF_DEBATE_HOME"] = tempfile.mkdtemp(prefix="pfd-test-")
os.environ["PF_DEBATE_EXPORTS"] = tempfile.mkdtemp(prefix="pfd-exports-")

import pytest  # noqa: E402

ARTICLE = (
    "<html><head><title>Data Centers and the Grid</title><meta name='author' content='Jane Smith'>"
    "<meta property='article:published_time' content='2025-03-01'></head><body><article>"
    + "".join(
        f"<p>Paragraph {i}: Data centers consumed about 4.4 percent of total U.S. electricity in 2023, "
        f"and analysts expect that share to keep rising as hyperscale facilities come online. "
        f"Local grids in Virginia and Texas are already strained by the new load.</p>"
        for i in range(6)
    )
    + "</article></body></html>"
)

PAGES = {
    "/article": ("text/html", ARTICLE.encode()),
    "/corrupt.pdf": ("application/pdf", b"%PDF-1.7\n this is not really a pdf \n%%EOF"),
    "/short": ("text/html", b"<html><body><p>Subscribe to read.</p></body></html>"),
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib naming)
        page = PAGES.get(self.path)
        if not page:
            self.send_response(404)
            self.end_headers()
            return
        ctype, body = page
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def web():
    """Base URL of a local test web server (html article, corrupt pdf, paywall-like short page)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="session")
def tiny_library():
    """A 3-card library.db in the temp home."""
    import zlib

    from pf_debate_mcp import library

    con = library._connect()
    rows = [
        (1, "b1", 900, "cx", 2019, "N", "HS CX", "Economic decline causes nuclear war", "Harris 09",
         "Harris 09 [fellow]", "Impacts", "economic decline increases the risk of great power war"),
        (2, "b2", 3, "pf", 2021, "A", "HS PF", "Data centers raise electricity bills", "Lee 21",
         "Lee 21 [reporter]", "C1", "utility bills rose as data centers added load"),
        (3, "b3", 40, "ld", 2020, "N", "HS LD", "Nuclear war causes extinction", "Robock 20",
         "Robock 20 [professor]", "Impacts", "nuclear winter would cause global famine"),
    ]
    for r in rows:
        markup = f"<h4>{r[7]}</h4><p><strong>{r[8]}</strong></p><p>Context <u><mark>{r[11]}</mark></u>.</p>"
        con.execute("insert or ignore into cards values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*r[:10], r[10], r[11], zlib.compress(markup.encode())))
        con.execute("insert into fts(rowid, tag, cite, heads, spoken) values (?,?,?,?,?)",
                    (r[0], r[7], r[8], r[10], r[11]))
    con.commit()
    return library
