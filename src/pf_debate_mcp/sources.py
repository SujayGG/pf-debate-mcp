"""Fetch a web page or PDF into clean text + citation metadata."""

import io
import ipaddress
import re
import socket

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


_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")  # zero-width / bidi tricks
MAX_BYTES = {True: 15_000_000, False: 100_000_000}  # hosted vs local download cap
ALLOWED_PORTS = {None, 80, 443}
_resolve = socket.getaddrinfo  # the guard's own resolver reference (tests swap it)


def check_public(url: str) -> None:
    """SSRF guard for the shared server: only http(s) on standard ports, and only to public addresses.
    Runs on every request hop (redirects included) via an httpx event hook."""
    u = httpx.URL(url)
    if u.scheme not in ("http", "https") or u.port not in ALLOWED_PORTS:
        raise FetchError("Only http(s) web addresses on standard ports can be fetched.")
    try:
        infos = _resolve(u.host, u.port or (443 if u.scheme == "https" else 80))
    except OSError:
        raise FetchError(f"Couldn't resolve {u.host}. Check the URL.") from None
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise FetchError("That address is private or internal, so the server won't fetch it.")
    # ponytail: DNS is resolved again by httpx after this check (rebinding window); pin the IP if abused


def fetch(url: str, block_private: bool = False) -> tuple[dict, str]:
    hooks = {"request": [lambda req: check_public(str(req.url))]} if block_private else {}
    try:
        with httpx.Client(headers={"User-Agent": _UA}, follow_redirects=True, max_redirects=5, timeout=30,
                          event_hooks=hooks) as client, client.stream("GET", url) as r:
            if r.status_code >= 400:
                raise FetchError(f"{url} returned HTTP {r.status_code} (blocked or paywalled). Try another source.")
            ctype = r.headers.get("content-type", "")
            if block_private and not any(t in ctype for t in ("html", "pdf", "text", "xml")) and ctype:
                raise FetchError(f"Unsupported content type ({ctype.split(';')[0]}). Use an article or PDF.")
            body = bytearray()
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES[block_private]:
                    raise FetchError("That file is too large to fetch. Try a shorter article or a direct PDF link.")
            final_url = str(r.url)
            encoding = r.encoding or "utf-8"
    except httpx.HTTPError as e:
        raise FetchError(f"Could not reach {url}: {type(e).__name__}. Try another source.") from None
    data = bytes(body)
    is_pdf = "pdf" in ctype or data[:5] == b"%PDF-"
    try:
        meta, text = _pdf(data) if is_pdf else _html(data.decode(encoding, errors="replace"), final_url)
    except (PyPdfError, ValueError, UnicodeDecodeError) as e:  # corrupt PDF / undecodable page
        kind = "PDF" if is_pdf else "page"
        raise FetchError(f"Couldn't read this {kind} ({type(e).__name__}). Try another source.") from None
    text = _INVISIBLE.sub("", re.sub(r"[ \t]+", " ", text)).strip()
    if len(text) < 600:
        raise FetchError(f"Only {len(text)} characters extracted from {url}: likely a paywall, login wall, "
                         "or JavaScript-only page. Try another source (never cut from memory).")
    meta["url"] = final_url
    return meta, text


def paragraphs(text: str) -> list[str]:
    return [t for _, t in paragraph_spans(text)]
