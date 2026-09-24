"""Tests for discovery.find_sources: OpenAlex (papers), GDELT/Google News RSS (news).
All network calls go to the local `web` fixture or are monkeypatched -- no real internet."""

import json
from urllib.parse import urlencode

import httpx
import pytest

from pf_debate_mcp import discovery

from conftest import PAGES


def test_openalex_mapping_abstract_and_quals(web, monkeypatch):
    query = "quantum computing advances"
    params = {"search": query, "per-page": 3, "filter": "has_abstract:true",
              "sort": "relevance_score:desc", "mailto": discovery.MAILTO}
    work = {
        "title": "Quantum Advantage in NISQ Devices",
        "doi": "https://doi.org/10.1000/xyz",
        "id": "https://openalex.org/W123",
        "best_oa_location": {"landing_page_url": "https://example.org/paper",
                              "pdf_url": "https://example.org/paper.pdf"},
        "authorships": [
            {"author": {"display_name": "Alice Smith"},
             "institutions": [{"display_name": "MIT"}, {"display_name": "Google Research"}]},
            {"author": {"display_name": "Bob Lee"}, "institutions": []},
        ],
        "primary_location": {"source": {"display_name": "Nature Physics"}},
        "publication_date": "2024-05-01",
        "abstract_inverted_index": {"Quantum": [0], "computers": [1], "may": [2],
                                     "outperform": [3], "classical": [4], "machines.": [5]},
    }
    monkeypatch.setattr(discovery, "OPENALEX", f"{web}/openalex")
    PAGES[f"/openalex?{urlencode(params)}"] = ("application/json", json.dumps({"results": [work]}).encode())

    result = discovery.find_sources(query, kinds=("papers",), limit=3)

    assert result["skipped"] == []
    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["kind"] == "paper"
    assert r["title"] == "Quantum Advantage in NISQ Devices"
    assert r["url"] == "https://example.org/paper"  # best_oa_location wins over doi/id
    assert r["pdf_url"] == "https://example.org/paper.pdf"
    assert r["authors"] == ["Alice Smith", "Bob Lee"]
    assert r["quals"] == "MIT, Google Research"  # first author's institutions only
    assert r["date"] == "2024-05-01"
    assert r["source"] == "Nature Physics"
    assert r["snippet"] == "Quantum computers may outperform classical machines."
    assert len(r["snippet"]) <= 300


def test_gdelt_failure_falls_back_to_google_news(web, monkeypatch):
    query = "election fraud claims"
    gdelt_params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": 5, "sort": "DateDesc"}
    gnews_params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    rss = (
        "<?xml version='1.0'?><rss version='2.0'><channel>"
        "<item><title>Big News Story</title><link>https://news.example.com/story</link>"
        "<pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate>"
        "<source url='https://news.example.com'>Example News</source></item>"
        "</channel></rss>"
    )
    monkeypatch.setattr(discovery, "GDELT", f"{web}/gdelt-bad")
    monkeypatch.setattr(discovery, "GNEWS", f"{web}/gnews-ok")
    PAGES[f"/gdelt-bad?{urlencode(gdelt_params)}"] = ("text/plain", b"Error: too many requests")
    PAGES[f"/gnews-ok?{urlencode(gnews_params)}"] = ("application/xml", rss.encode())

    result = discovery.find_sources(query, kinds=("news",), limit=5)

    assert any(s.startswith("gdelt:") for s in result["skipped"])
    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["kind"] == "news"
    assert r["title"] == "Big News Story"
    assert r["url"] == "https://news.example.com/story"
    assert r["date"] == "2025-09-01"
    assert r["source"] == "Example News"


def test_one_source_timeout_does_not_lose_the_others(web, monkeypatch):
    query = "fusion breakthrough claims"
    gdelt_params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": 4, "sort": "DateDesc"}
    articles = {"articles": [
        {"title": "A", "url": "https://n.com/a", "seendate": "20250101T000000Z", "domain": "n.com"},
        {"title": "B", "url": "https://n.com/b", "seendate": "20250102T000000Z", "domain": "n.com"},
    ]}  # 2 hits at limit//2==2 is enough that gnews fallback isn't needed
    monkeypatch.setattr(discovery, "GDELT", f"{web}/gdelt-ok2")
    PAGES[f"/gdelt-ok2?{urlencode(gdelt_params)}"] = ("application/json", json.dumps(articles).encode())

    def timeout(query, n):
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(discovery, "_fetch_papers", timeout)

    result = discovery.find_sources(query, kinds=("papers", "news"), limit=4)

    assert any(s.startswith("openalex:") for s in result["skipped"])
    assert len(result["results"]) == 2
    assert all(r["kind"] == "news" for r in result["results"])
    assert result["results"][0]["date"] == "2025-01-02"  # newest first


def test_cache_returns_same_object_without_refetching(web, monkeypatch):
    query = "cache probe query unique"
    params = {"search": query, "per-page": 2, "filter": "has_abstract:true",
              "sort": "relevance_score:desc", "mailto": discovery.MAILTO}
    work = {"title": "Cached Paper", "id": "https://openalex.org/W1", "best_oa_location": {},
            "authorships": [], "primary_location": {}, "publication_date": "2024-01-01",
            "abstract_inverted_index": {}}
    monkeypatch.setattr(discovery, "OPENALEX", f"{web}/openalex-cache")
    PAGES[f"/openalex-cache?{urlencode(params)}"] = ("application/json", json.dumps({"results": [work]}).encode())

    calls = []
    real_get = discovery._get

    def counting_get(url):
        calls.append(url)
        return real_get(url)
    monkeypatch.setattr(discovery, "_get", counting_get)

    first = discovery.find_sources(query, kinds=("papers",), limit=2)
    second = discovery.find_sources(query, kinds=("papers",), limit=2)

    assert second is first  # same cached object, not just equal
    assert len(calls) == 1  # no HTTP request on the repeat call


def test_429_is_retried_once(monkeypatch):
    calls = []

    def fake_get(url, timeout=None, headers=None):
        calls.append(url)
        req = httpx.Request("GET", url)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, request=req)
        return httpx.Response(200, json={"results": []}, request=req)
    monkeypatch.setattr(httpx, "get", fake_get)

    r = discovery._get("http://example.test/works?search=x")

    assert r.status_code == 200
    assert len(calls) == 2
