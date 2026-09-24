"""Storage for fetched sources, the user's cards, and (hosted) exported files.

Local mode: SQLite at ~/.pf-debate/pf.db; ids look like s12 / c34 and last forever.
Hosted mode (one shared public server): nothing touches disk and nothing is tied to a session.
Sources, cards and exports live in byte-bounded in-memory LRUs under random ids (s_…, c_…),
so students can't read each other's work, and memory stays bounded however many use it.
A restart or eviction simply makes an id unknown; the tools then say "fetch/cut again".
"""

import json
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path

from .cards import Run, runs_from_ranges

HOME = Path(os.environ.get("PF_DEBATE_HOME") or Path.home() / ".pf-debate")
EXPORT_DIR = Path(os.environ.get("PF_DEBATE_EXPORTS") or Path.home() / "Documents" / "pf-debate")
HOSTED = False
PUBLIC_URL = ""

_SCHEMA = """
create table if not exists sources(
  id integer primary key, url text, title text, author text, date text, publisher text,
  text text not null, fetched_at text default current_timestamp);
create table if not exists cards(
  id integer primary key, tag text not null, cite_short text, cite_rest text, body text not null,
  underline text, highlight text, origin text, created_at text default current_timestamp);
"""


class _ByteLRU:
    """Thread-safe LRU that evicts oldest entries once their total size passes max_bytes."""

    def __init__(self, max_bytes: int, ttl: float | None = None):
        self.max_bytes, self.ttl, self.size = max_bytes, ttl, 0
        self.items: OrderedDict[str, tuple[float, int, object]] = OrderedDict()
        self.lock = threading.Lock()

    def put(self, key: str, value: object, nbytes: int) -> None:
        with self.lock:
            self.items[key] = (time.time(), nbytes, value)
            self.size += nbytes
            while self.size > self.max_bytes and len(self.items) > 1:
                _, (_, n, _) = self.items.popitem(last=False)
                self.size -= n

    def get(self, key: str):
        with self.lock:
            hit = self.items.get(key)
            if not hit or (self.ttl and time.time() - hit[0] > self.ttl):
                return None
            self.items.move_to_end(key)
            return hit[2]


_sources = _ByteLRU(1_000_000_000)  # fetched page text (pages are capped at 15 MB each)
_cards = _ByteLRU(150_000_000)
_files = _ByteLRU(200_000_000, ttl=3600)  # exported docs, downloadable for 1 hour
_urls = _ByteLRU(20_000_000)  # hosted: url -> source id, so refetching a page reuses it


def enable_hosted(public_url: str) -> None:
    global HOSTED, PUBLIC_URL
    HOSTED, PUBLIC_URL = True, public_url.rstrip("/")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


_local = threading.local()  # one connection per thread: MCP tools run in a thread pool


def db() -> sqlite3.Connection:
    con = getattr(_local, "con", None)
    if con is None:
        HOME.mkdir(parents=True, exist_ok=True)
        con = _local.con = sqlite3.connect(HOME / "pf.db", timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("pragma journal_mode=wal")
        con.executescript(_SCHEMA)
    return con


def _local_id(sid: str, prefix: str) -> int | None:
    m = re.fullmatch(prefix + r"(\d+)", sid)
    return int(m[1]) if m else None


def add_source(url: str, meta: dict, text: str) -> str:
    if HOSTED:
        sid = _new_id("s")
        _sources.put(sid, {**meta, "url": meta.get("url") or url, "text": text}, len(text))
        _urls.put(url, sid, len(url))
        return sid
    with db() as con:
        cur = con.execute(
            "insert into sources(url, title, author, date, publisher, text) values (?,?,?,?,?,?)",
            (url, meta.get("title"), meta.get("author"), meta.get("date"), meta.get("publisher"), text),
        )
    return f"s{cur.lastrowid}"


def get_source(sid: str) -> dict | None:
    """{url, title, author, date, publisher, text} or None if unknown/expired."""
    if HOSTED:
        return _sources.get(sid)
    n = _local_id(sid, "s")
    row = n is not None and db().execute("select * from sources where id=?", (n,)).fetchone()
    return dict(row) if row else None


def find_source(url: str) -> tuple[str, dict] | None:
    if HOSTED:
        sid = _urls.get(url)
        src = sid and _sources.get(sid)
        return (sid, src) if src else None
    row = db().execute("select * from sources where url=? order by id desc", (url,)).fetchone()
    return (f"s{row['id']}", dict(row)) if row else None


def add_card(tag: str, cite_short: str, cite_rest: str, body: str, underline, highlight, origin: str) -> str:
    if HOSTED:
        cid = _new_id("c")
        card = {"tag": tag, "cite_short": cite_short, "cite_rest": cite_rest, "body": body,
                "underline": underline, "highlight": highlight, "origin": origin}
        _cards.put(cid, card, len(body) + len(cite_rest) + len(tag))
        return cid
    with db() as con:
        cur = con.execute(
            "insert into cards(tag, cite_short, cite_rest, body, underline, highlight, origin) values (?,?,?,?,?,?,?)",
            (tag, cite_short, cite_rest, body, json.dumps(underline), json.dumps(highlight), origin),
        )
    return f"c{cur.lastrowid}"


def get_card(cid: str) -> dict | None:
    if HOSTED:
        r = _cards.get(cid)
        underline, highlight = (r["underline"], r["highlight"]) if r else (None, None)
    else:
        n = _local_id(cid, "c")
        r = n is not None and db().execute("select * from cards where id=?", (n,)).fetchone()
        underline, highlight = (json.loads(r["underline"]), json.loads(r["highlight"])) if r else (None, None)
    if not r:
        return None
    runs: list[Run] = runs_from_ranges(r["body"], [tuple(x) for x in underline], [tuple(x) for x in highlight])
    return {"id": cid, "tag": r["tag"], "cite_short": r["cite_short"], "cite_rest": r["cite_rest"],
            "runs": runs, "origin": r["origin"]}


def search_cards(query: str, limit: int) -> list[dict]:
    words = re.findall(r"\w+", query.lower())
    if not words:
        return []
    where = " and ".join("lower(tag || ' ' || cite_short || ' ' || body) like ?" for _ in words)
    rows = db().execute(
        f"select id, tag, cite_short, substr(body, 1, 200) snippet, origin from cards where {where} "
        "order by id desc limit ?",
        [*(f"%{w}%" for w in words), limit],
    ).fetchall()
    return [dict(r) | {"id": f"c{r['id']}"} for r in rows]


def save_export(filename: str, data: bytes) -> str:
    """Hosted: keep an exported file for an hour and return its download URL."""
    token = secrets.token_urlsafe(16)
    _files.put(token, (filename, data), len(data))
    return f"{PUBLIC_URL}/files/{token}/{filename}"


def get_export(token: str) -> tuple[str, bytes] | None:
    return _files.get(token)
