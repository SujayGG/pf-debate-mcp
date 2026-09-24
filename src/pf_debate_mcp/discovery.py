"""Find citable, credentialed evidence: papers (OpenAlex) and news (GDELT, falling back to
Google News RSS). Free, keyless, adds no dependencies beyond httpx (already required).

Papers and news are fetched in parallel (each source gets its own thread and an 8s timeout);
a source that fails or times out is reported in "skipped" rather than losing the others' results.
"""

import concurrent.futures as cf
import json
import os
import re
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import httpx

from .store import _ByteLRU

OPENALEX = "https://api.openalex.org/works"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
GNEWS = "https://news.google.com/rss/search"
BING = "https://www.bing.com/news/search"
GUARDIAN = "https://content.guardianapis.com/search"
DECODE_GNEWS = True
MAILTO = "pf-debate@users.noreply.github.com"
TIMEOUT = 8.0  # seconds per source; sources run in parallel
_HEADERS = {"User-Agent": "pf-debate-mcp (citable evidence search)"}

_cache = _ByteLRU(20_000_000, ttl=3600)  # (query, kinds, limit) -> {"results", "skipped"}, 1h


def _url(base: str, params: dict) -> str:
    return f"{base}?{urlencode(params)}"


def _get(url: str) -> httpx.Response:
    """GET with one retry on 429, honoring Retry-After (capped at 5s so a lazy server can't stall us)."""
    r = httpx.get(url, timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True)
    if r.status_code == 429:
        time.sleep(min(float(r.headers.get("Retry-After", 1)), 5.0))
        r = httpx.get(url, timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True)
    r.raise_for_status()
    return r


def _reason(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    return str(e) or type(e).__name__


# ---- papers: OpenAlex --------------------------------------------------

def _abstract(inv_index: dict | None) -> str:
    """OpenAlex ships abstracts as a word -> [positions] inverted index; rebuild the text."""
    if not inv_index:
        return ""
    length = max(p for positions in inv_index.values() for p in positions) + 1
    words = [""] * length
    for word, positions in inv_index.items():
        for p in positions:
            words[p] = word
    return " ".join(w for w in words if w)[:300]


def _map_paper(w: dict) -> dict:
    best = w.get("best_oa_location") or {}
    url = best.get("landing_page_url") or w.get("doi") or w.get("id")
    authorships = w.get("authorships") or []
    authors = [a["author"]["display_name"] for a in authorships[:4] if a.get("author", {}).get("display_name")]
    quals = None
    if authorships:
        insts = authorships[0].get("institutions") or []
        quals = ", ".join(i["display_name"] for i in insts if i.get("display_name")) or None
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    return {"kind": "paper", "title": w.get("title"), "url": url, "authors": authors, "quals": quals,
            "date": w.get("publication_date"), "source": source,
            "snippet": _abstract(w.get("abstract_inverted_index")), "pdf_url": best.get("pdf_url")}


def _fetch_papers(query: str, n: int) -> list[dict]:
    params = {"search": query, "per-page": n, "filter": "has_abstract:true,from_publication_date:2015-01-01",
              "sort": "relevance_score:desc", "mailto": MAILTO}
    data = _get(_url(OPENALEX, params)).json()
    return [_map_paper(w) for w in data.get("results", [])]


# ---- news: GDELT, falling back to Google News RSS ----------------------

def _map_gdelt(a: dict) -> dict:
    seen = a.get("seendate") or ""
    date = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) >= 8 else None
    return {"kind": "news", "title": a.get("title"), "url": a.get("url"), "authors": [], "quals": None,
            "date": date, "source": a.get("domain"), "snippet": ""}


_gdelt_lock = threading.Lock()
_gdelt_last = [0.0]
GDELT_GAP = 5.2  # GDELT allows one request per 5 s per IP; everyone on this server shares that pace


def _fetch_gdelt(query: str, n: int) -> list[dict]:
    with _gdelt_lock:  # queue requests instead of tripping GDELT's 429
        wait = _gdelt_last[0] + GDELT_GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        _gdelt_last[0] = time.time()
    params = {"query": f"{query} sourcelang:english", "mode": "ArtList", "format": "json", "maxrecords": n,
              "sort": "HybridRel"}
    r = _get(_url(GDELT, params))
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError("non-JSON response") from None  # GDELT returns plain-text errors, not JSON
    return [_map_gdelt(a) for a in data.get("articles", [])]


def _rfc822_date(s: str) -> str | None:
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/140.0 Safari/537.36"}


def decode_gnews(link: str) -> str | None:
    """Google News RSS links are opaque redirects; ask Google for the real article URL (unofficial: same
    two calls the Google News web page makes). Returns None if Google changes the format."""
    try:
        aid = link.split("/articles/")[1].split("?")[0]
        page = httpx.get(f"https://news.google.com/articles/{aid}", headers=_BROWSER, timeout=TIMEOUT,
                         follow_redirects=True).text
        sg = re.search(r"data-n-a-sg=[\"']([^\"']+)", page)
        ts = re.search(r"data-n-a-ts=[\"']([^\"']+)", page)
        if not (sg and ts):
            return None
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None,
                                 None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                 aid, int(ts.group(1)), sg.group(1)]
        r = httpx.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                       data={"f.req": json.dumps([[["Fbv4je", json.dumps(inner)]]])},
                       headers={**_BROWSER, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                       timeout=TIMEOUT)
        return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]
    except (httpx.HTTPError, IndexError, ValueError, TypeError):
        return None


def _fetch_gnews(query: str, n: int) -> list[dict]:
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    root = ET.fromstring(_get(_url(GNEWS, params)).text)
    out = []
    for item in root.findall(".//item")[:n]:
        source_el = item.find("source")
        out.append({"kind": "news", "title": (item.findtext("title") or "").strip(),
                    "url": (item.findtext("link") or "").strip(), "authors": [], "quals": None,
                    "date": _rfc822_date(item.findtext("pubDate") or ""),
                    "source": source_el.text if source_el is not None else None, "snippet": ""})
    if DECODE_GNEWS:  # turn Google's redirect links into real article URLs (in parallel); drop failures
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            real = list(ex.map(lambda it: decode_gnews(it["url"]), out))
        out = [{**it, "url": u} for it, u in zip(out, real) if u]
    return out


def _fetch_guardian(query: str, n: int) -> list[dict]:
    """The Guardian Open Platform: full article text in the API response, so no fetching or paywalls.
    Needs a free key (GUARDIAN_API_KEY); without one this source is skipped."""
    key = os.environ.get("GUARDIAN_API_KEY")
    if not key:
        return []
    d = _get(_url(GUARDIAN, {"q": query, "page-size": n, "order-by": "relevance", "api-key": key,
                             "show-fields": "bodyText,byline,trailText"})).json()["response"]
    return [{"kind": "news", "title": a.get("webTitle"), "url": a.get("webUrl"),
             "authors": [a["fields"]["byline"]] if a.get("fields", {}).get("byline") else [], "quals": None,
             "date": (a.get("webPublicationDate") or "")[:10], "source": "The Guardian",
             "snippet": a.get("fields", {}).get("trailText", "")[:300], "text": a.get("fields", {}).get("bodyText")}
            for a in d.get("results", [])]


def _fetch_bing(query: str, n: int) -> list[dict]:
    """Bing News RSS: unlike Google News, its links carry the real article URL (in the url= parameter)."""
    from urllib.parse import parse_qs, urlparse

    root = ET.fromstring(_get(_url(BING, {"q": query, "format": "rss"})).text)
    out = []
    for item in root.findall(".//item")[:n]:
        link = (item.findtext("link") or "").strip()
        real = parse_qs(urlparse(link).query).get("url", [link])[0]
        out.append({"kind": "news", "title": (item.findtext("title") or "").strip(), "url": real, "authors": [],
                    "quals": None, "date": _rfc822_date(item.findtext("pubDate") or ""),
                    "source": urlparse(real).netloc.removeprefix("www."),
                    "snippet": (item.findtext("description") or "")[:300]})
    return out


# ---- orchestration -------------------------------------------------------

def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in items:
        u = it.get("url")
        if u and u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


def find_sources(query: str, kinds: tuple[str, ...] = ("papers", "news"), limit: int = 10) -> dict:
    """Search OpenAlex for papers and GDELT/Google News for news, for debaters who need citable,
    credentialed evidence (not chat answers). Runs selected sources in parallel; a failed source
    is skipped, not fatal. Results: papers first (by relevance), then news (newest first), each
    capped at `limit` and deduped by URL. Cached for 1h per (query, kinds, limit)."""
    key = f"{query}\n{sorted(kinds)}\n{limit}"
    if (hit := _cache.get(key)) is not None:
        return hit

    jobs = [("openalex", _fetch_papers)] if "papers" in kinds else []
    if "news" in kinds:
        jobs += [("gdelt", _fetch_gdelt), ("bing", _fetch_bing), ("gnews", _fetch_gnews), ("guardian", _fetch_guardian)]

    got, skipped = {}, []
    with cf.ThreadPoolExecutor(max_workers=max(1, len(jobs))) as ex:
        futs = {ex.submit(fn, query, limit): name for name, fn in jobs}
        for fut, name in futs.items():
            try:
                got[name] = fut.result()
            except Exception as e:
                skipped.append(f"{name}: {_reason(e)}")

    papers = _dedupe(got.get("openalex", []))[:limit] if "papers" in kinds else []

    news = []
    if "news" in kinds:
        news = got.get("guardian", []) + got.get("gdelt", []) + got.get("bing", []) + got.get("gnews", [])
        news = sorted(_dedupe(news), key=lambda x: x.get("date") or "", reverse=True)[:limit]

    result = {"results": papers + news, "skipped": skipped}
    _cache.put(key, result, len(json.dumps(result, default=str)))
    return result
