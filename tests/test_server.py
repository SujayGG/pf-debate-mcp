"""Tool-level tests through the real MCP tool layer (mcp.call_tool), so error flags match what agents see."""

import asyncio
import threading

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from pf_debate_mcp import caselist, library, store
from pf_debate_mcp.server import mcp


def call(name, **args):
    result = asyncio.run(mcp.call_tool(name, args))
    return "\n".join(b.text for b in result.content)


def cite(**over):
    return {"author": "Jane Smith", "date": "2025-03-01", "title": "Data Centers and the Grid",
            "publisher": "Test Times", "url": "http://example.test", "quals": "energy reporter", **over}


# --- regressions (behavior changed in step 1) --------------------------------------------------

def test_search_never_calls_status(tiny_library, monkeypatch):
    monkeypatch.setattr(library, "status", lambda: pytest.fail("search must not call status() (843 ms)"))
    out = call("search_cards", query="nuclear war", sort="popular")
    assert "lib:1" in out and out.index("lib:1") < out.index("lib:3")  # popular: 900 reads before 40


def test_missing_card_is_a_readable_error():
    with pytest.raises(ToolError, match="c999 not found"):
        call("get_card", card_id="c999")


def test_rejected_cut_is_an_error_not_a_result(web):
    sid = call("fetch_source", url_or_id=f"{web}/article").split("source_id: ")[1].split()[0]
    with pytest.raises(ToolError, match="REJECTED"):
        call("cut_card", source_id=sid, tag="x", start_quote="Paragraph 0:", end_quote="new load.",
             highlight=["grids will collapse tomorrow"], **cite())


def test_ambiguous_start_quote_needs_paragraph(web):
    sid = call("fetch_source", url_or_id=f"{web}/article").split("source_id: ")[1].split()[0]
    with pytest.raises(ToolError, match="appears 6 times"):
        call("cut_card", source_id=sid, tag="x", start_quote="Data centers consumed", end_quote="new load.",
             highlight=["4.4 percent"], **cite())
    out = call("cut_card", source_id=sid, tag="Data centers strain grids", start_quote="Data centers consumed",
               end_quote="new load.", highlight=["4.4 percent"], paragraph=2, **cite())
    assert "Saved as c" in out


# --- fetching ----------------------------------------------------------------------------------

def test_fetch_article_numbers_paragraphs(web):
    out = call("fetch_source", url_or_id=f"{web}/article")
    assert "[0] Paragraph 0:" in out and "[5] Paragraph 5:" in out


def test_corrupt_pdf_is_named(web):
    with pytest.raises(ToolError, match="Couldn't read this PDF"):
        call("fetch_source", url_or_id=f"{web}/corrupt.pdf")


def test_paywall_like_page(web):
    with pytest.raises(ToolError, match="paywall"):
        call("fetch_source", url_or_id=f"{web}/short")


def test_caselist_network_error_is_named(monkeypatch):
    monkeypatch.setattr(caselist, "API", "http://127.0.0.1:9")  # nothing listens on the discard port
    monkeypatch.setattr(caselist, "_token", lambda: "t")
    with pytest.raises(caselist.CaselistError, match="Network problem"):
        caselist.search("anything", "hspf26")


# --- views and exports -------------------------------------------------------------------------

def test_get_card_read_view_is_compact(tiny_library):
    read = call("get_card", card_id="lib:1")
    full = call("get_card", card_id="lib:1", view="full")
    assert "==economic decline" in read and "Context" not in read and "Context" in full


def test_export_gdocs_html(tiny_library):
    out = call("export_doc", title="Neg Case", items=[{"pocket": "Neg"}, {"card": "lib:1"}], format="gdocs")
    path = out.split("Saved ")[1].split(" (")[0]
    page = open(path, encoding="utf-8").read()
    assert "<h1>Neg</h1>" in page and "background-color:#00ffff" in page and "Harris 09" in page


def test_export_rejects_bad_item():
    with pytest.raises(ToolError, match="Bad item"):
        call("export_doc", title="x", items=[{"pocket": "a", "hat": "b"}])


# --- concurrency (tools run in a thread pool) --------------------------------------------------

def test_concurrent_card_writes():
    errors, ids = [], []

    def work(i):
        try:
            ids.append(store.add_card(f"tag {i}", "S 25", "[cite]", f"body {i}.", [(0, 4)], [(0, 4)], "test"))
        except Exception as e:  # collected and asserted below
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(set(ids)) == 20


def test_concurrent_library_search(tiny_library):
    errors = []

    def work():
        try:
            assert library.search("nuclear war")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=work) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
