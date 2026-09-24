import pytest

from pf_debate_mcp.cards import CutError, cut, runs_from_ranges

SOURCE = (
    "Data centers consumed about 4.4 percent of total U.S. electricity in 2023. "
    "By 2028, that share could rise to between 6.7 and 12 percent, according to the report. "
    "“Hyperscale facilities are driving most of that growth,” the authors wrote. "
    "Local grids in Virginia and Texas are already strained."
)


def test_cuts_verbatim_body_and_marks():
    card = cut(
        SOURCE,
        start_quote="Data centers consumed",
        end_quote="according to the report.",
        underline=["consumed about 4.4 percent", "could rise to between 6.7 and 12 percent"],
        highlight=["4.4 percent", "6.7 and 12 percent"],
    )
    assert card["body"].startswith("Data centers consumed")
    assert card["body"].endswith("according to the report.")
    hl = [card["body"][s:e] for s, e in card["highlight"]]
    assert hl == ["4.4 percent", "6.7 and 12 percent"]


def test_rejects_changed_word():
    with pytest.raises(CutError, match="not found"):
        cut(SOURCE, "Data centers consumed about 5 percent", "report.", [], ["about 5 percent"])


def test_rejects_invented_highlight():
    with pytest.raises(CutError, match="highlight"):
        cut(SOURCE, "Data centers", "the report.", [], ["grids will collapse"])


def test_rejects_highlight_outside_body():
    # "Local grids" exists in the source but not inside the chosen body
    with pytest.raises(CutError, match="highlight"):
        cut(SOURCE, "Data centers", "the report.", [], ["Local grids"])


def test_normalizes_quotes_dashes_whitespace():
    card = cut(
        SOURCE,
        start_quote='"Hyperscale   facilities',
        end_quote="the authors wrote.",
        underline=[],
        highlight=['"Hyperscale facilities are driving most of that growth,"'],
    )
    # stored text is the original source text, curly quotes intact
    assert card["body"].startswith("“Hyperscale")


def test_error_hints_where_match_stops():
    with pytest.raises(CutError) as e:
        cut(SOURCE, "Data centers consumed about 9 percent", "report.", [], ["x"])
    assert "Data centers consumed about" in str(e.value)


def test_requires_highlight():
    with pytest.raises(CutError, match="highlight"):
        cut(SOURCE, "Data centers", "the report.", [], [])


def test_warns_on_highlight_not_underlined():
    card = cut(SOURCE, "Data centers", "the report.", ["consumed about"], ["4.4 percent"])
    assert any("not underlined" in w for w in card["warnings"])


def test_runs_from_ranges():
    runs = runs_from_ranges("abcdef", [(0, 4)], [(2, 4)])
    assert runs == [("ab", True, False), ("cd", True, True), ("ef", False, False)]


def test_ambiguous_start_rejected_with_paragraphs():
    text = "Intro: data centers use 4 percent. Critics disagree.\nLater: data centers use 4 percent. Growth is certain."
    with pytest.raises(CutError, match=r"appears 2 times \(paragraphs \[0, 1\]\)"):
        cut(text, "data centers use", "certain.", [], ["4 percent"])
    card = cut(text, "data centers use", "certain.", [], ["Growth is certain"], paragraph=1)
    assert card["body"].startswith("data centers use 4 percent. Growth")
    with pytest.raises(CutError, match=r"not in paragraph \[3\]"):
        cut(text, "data centers use", "certain.", [], ["4 percent"], paragraph=3)


def test_render_read_keeps_only_marked_text():
    from pf_debate_mcp.cards import render_read
    card = {"id": "c1", "tag": "T", "cite_short": "S 25", "cite_rest": "[x]",
            "runs": [("skip ", False, False), ("read this", True, True), (" filler ", False, False),
                     ("context", True, False)]}
    assert render_read(card).endswith("==read this== ... _context_")


def test_short_cite_names():
    from pf_debate_mcp.cards import format_cite
    base = {"date": "November 15, 2023", "quals": "q", "url": "u"}
    assert format_cite({**base, "author": "Abbasi et al."})[0] == "Abbasi et al. 23"
    assert format_cite({**base, "author": "Jane Smith and Bo Lee"})[0] == "Smith et al. 23"
    assert format_cite({**base, "author": "U.S. Department of Energy"})[0] == "U.S. Department of Energy 23"
