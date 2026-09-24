"""Fetch a web page or PDF into clean text + citation metadata."""

import io
import re

import httpx
import trafilatura
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .cards import paragraph_spans

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")


class FetchError(RuntimeError):
    pass


def _pdf(data: bytes) -> tuple[dict, str]:
    reader = PdfReader(io.BytesIO(data))
    info = reader.metadata or {}
    pages = [p.extract_text() or "" for p in reader.pages]
    text = "\n\n".join(pages)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # re-join words hyphenated across lines
    text = re.sub(r"(?<![.!?:\n])\n(?!\n)", " ", text)  # soft line breaks inside paragraphs
    meta = {"title": info.get("/Title"), "author": info.get("/Author"), "date": None, "publisher": None}
    created = str(info.get("/CreationDate") or "")
    if m := re.match(r"D:(\d{4})(\d{2})?(\d{2})?", created):
        meta["date"] = "-".join(g for g in m.groups() if g)
    return meta, text


def _html(html: str, url: str) -> tuple[dict, str]:
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False,
                               favor_precision=True) or ""
    md = trafilatura.extract_metadata(html, default_url=url)
    meta = {"title": md.title, "author": md.author, "date": md.date, "publisher": md.sitename} if md else {}
    return meta, text


def fetch(url: str) -> tuple[dict, str]:
    try:
        r = httpx.get(url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=30)
    except httpx.HTTPError as e:
        raise FetchError(f"Could not reach {url}: {e}") from None
    if r.status_code >= 400:
        raise FetchError(f"{url} returned HTTP {r.status_code} (blocked or paywalled). Try another source.")
    is_pdf = "pdf" in r.headers.get("content-type", "") or r.content[:5] == b"%PDF-"
    try:
        meta, text = _pdf(r.content) if is_pdf else _html(r.text, str(r.url))
    except (PyPdfError, ValueError, UnicodeDecodeError) as e:  # corrupt PDF / undecodable page
        kind = "PDF" if is_pdf else "page"
        raise FetchError(f"Couldn't read this {kind} ({type(e).__name__}). Try another source.") from None
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 600:
        raise FetchError(f"Only {len(text)} characters extracted from {url}: likely a paywall, login wall, "
                         "or JavaScript-only page. Try another source (never cut from memory).")
    meta["url"] = str(r.url)
    return meta, text


def paragraphs(text: str) -> list[str]:
    return [t for _, t in paragraph_spans(text)]
