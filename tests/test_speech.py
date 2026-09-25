"""Exact speech timing and the read-ready (Rhetorify) version."""

import io

import pytest
from docx import Document

from pf_debate_mcp import server, speech, store

BODY = "Unread lead in. Data centers raise bills for families. More unread text here. Regulators confirm it."


@pytest.fixture
def card_id():
    hl = [(BODY.index(s), BODY.index(s) + len(s)) for s in ("Data centers raise bills for families",
                                                            "Regulators confirm it")]
    return store.add_card("Grids cost more", "Kim 26", "[Greg Kim; Seattle Times]", BODY, hl, hl, "test")


def test_card_reads_tag_cite_and_highlight_only(card_id):
    lines = speech.script(server._resolve([{"card": card_id}]))
    assert lines[1][1] == "Kim 26: Data centers raise bills for families Regulators confirm it"
    assert sum(n for _, _, n in lines) == 3 + 2 + 9  # tag + "Kim 26:" + highlighted words


def test_report_times_sections_and_flags_overtime(card_id):
    items = [{"pocket": "Pro"}, {"hat": "Contention 1: Grid"}, {"text": "word " * 612}, {"card": card_id},
             {"hat": "Framing"}, {"text": "weigh " * 50}]
    out = server.read_speech(items, "constructive", 160)  # 3 + 612 + 14 + 1 + 50 = 680 words = 4:15
    assert out.startswith("Constructive: 4:15 of 4:00 at 160 wpm (680 words). 0:15 OVER: cut about 40 words")
    assert "Contention 1: Grid: 3:55 (626 words)" in out and "Framing: 0:19 (50 words)" in out
    assert "Grids cost more" in out.split("Longest cards")[1]
    assert "Unread lead in" not in out


def test_fits_and_bad_input():
    assert "fits" in speech.report([{"text": "word " * 635}], "constructive", 160)
    with pytest.raises(ValueError, match="wpm"):
        speech.report([], "constructive", 5)
    with pytest.raises(ValueError, match="speech must be"):
        speech.report([], "closing", 160)


def test_read_version_doc(card_id):
    name, data = server.render_doc("Pro", [{"hat": "C1"}, {"card": card_id}], None, "docx", "read", 160)
    assert name.endswith("-read.docx")
    text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    assert "Reads in 0:06 at 160 words per minute (15 words)." in text and "C1 [0:05]" in text
    assert "Data centers raise bills" in text and "Unread lead in" not in text and "Seattle Times" not in text
