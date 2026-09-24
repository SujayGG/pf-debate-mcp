"""Plain-English search and auto-cut suggestions (downloads the small embedding model once, ~130 MB)."""

import pytest

from pf_debate_mcp import semantic
from pf_debate_mcp.cards import cut

SOURCE = "\n".join([
    "The city council met on Tuesday to discuss parking permits and a new bike lane on Main Street.",
    "Hyperscale data centers now consume a growing share of the regional grid, and utilities say "
    "residential customers are paying higher monthly bills to fund the new transmission lines those "
    "facilities require. Regulators estimate the average household bill rose eleven percent in two years.",
    "Separately, the school board approved a new lunch menu featuring more vegetables.",
])


@pytest.fixture(scope="module")
def indexed(tiny_library):
    semantic.build_index(log=lambda m: None)
    semantic._state["path"] = None  # force a reload of the fresh index
    assert semantic._loaded()
    return tiny_library


def test_plain_english_query_finds_card(indexed):
    # a full sentence whose words don't all appear in the card: keyword search alone finds nothing
    hits = semantic.hybrid_search("cards saying families pay more for electricity because of data centers", limit=3)
    assert hits and hits[0]["id"] == "lib:2"


def test_hybrid_respects_filters(indexed):
    hits = semantic.hybrid_search("nuclear war", event="ld", limit=5)
    assert hits and all(h["event"] == "ld" for h in hits)


def test_suggest_skips_headline_that_echoes_the_claim():
    text = "Data Centers Raise Household Electricity Bills\n" + SOURCE
    s = semantic.suggest(text, "data centers raise household electricity bills")
    assert s["paragraph"] == 2  # the reporting paragraph, not the headline at [0]


def test_suggest_picks_the_supporting_passage_and_passes_the_gate():
    s = semantic.suggest(SOURCE, "data centers raise household electricity bills")
    assert s["paragraph"] == 1
    card = cut(SOURCE, s["start_quote"], s["end_quote"], s["underline"], s["highlight"], s["paragraph"])
    assert "data centers" in card["body"] and "school board" not in card["body"]


def test_auto_cut_returns_verified_new_cards(indexed, web, monkeypatch):
    from pf_debate_mcp import discovery, server

    monkeypatch.setattr(discovery, "find_sources", lambda q, kinds, limit: {"results": [
        {"kind": "news", "title": "Data centers and the grid", "url": f"{web}/article", "date": "2025-03-01",
         "snippet": "data centers electricity"},
        {"kind": "news", "title": "Paywalled", "url": f"{web}/short", "date": "2025-03-01", "snippet": "x"}],
        "skipped": []})
    r = server.auto_cut_cards("data centers consume a growing share of U.S. electricity", 2)
    assert r["new"] and r["new"][0]["card"]["id"]  # cut and verified from the article
    assert any("short" in s.get("skipped", "") for s in r["skipped"] if isinstance(s, dict))  # paywall skipped
