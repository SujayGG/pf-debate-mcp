"""Local storage: fetched sources and the user's own cards (~/.pf-debate/pf.db)."""

import json
import os
import re
import sqlite3
from functools import cache
from pathlib import Path

from .cards import Run, runs_from_ranges

HOME = Path(os.environ.get("PF_DEBATE_HOME") or Path.home() / ".pf-debate")
EXPORT_DIR = Path(os.environ.get("PF_DEBATE_EXPORTS") or Path.home() / "Documents" / "pf-debate")

_SCHEMA = """
create table if not exists sources(
  id integer primary key, url text, title text, author text, date text, publisher text,
  text text not null, fetched_at text default current_timestamp);
create table if not exists cards(
  id integer primary key, tag text not null, cite_short text, cite_rest text, body text not null,
  underline text, highlight text, origin text, created_at text default current_timestamp);
"""


@cache
def db() -> sqlite3.Connection:
    HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(HOME / "pf.db", check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def add_source(url: str, meta: dict, text: str) -> int:
    with db() as con:
        cur = con.execute(
            "insert into sources(url, title, author, date, publisher, text) values (?,?,?,?,?,?)",
            (url, meta.get("title"), meta.get("author"), meta.get("date"), meta.get("publisher"), text),
        )
    return cur.lastrowid


def get_source(source_id: int) -> sqlite3.Row | None:
    return db().execute("select * from sources where id=?", (source_id,)).fetchone()


def find_source(url: str) -> sqlite3.Row | None:
    return db().execute("select * from sources where url=? order by id desc", (url,)).fetchone()


def add_card(tag: str, cite_short: str, cite_rest: str, body: str, underline, highlight, origin: str) -> int:
    with db() as con:
        cur = con.execute(
            "insert into cards(tag, cite_short, cite_rest, body, underline, highlight, origin) values (?,?,?,?,?,?,?)",
            (tag, cite_short, cite_rest, body, json.dumps(underline), json.dumps(highlight), origin),
        )
    return cur.lastrowid


def get_card(card_id: int) -> dict | None:
    r = db().execute("select * from cards where id=?", (card_id,)).fetchone()
    if not r:
        return None
    runs: list[Run] = runs_from_ranges(r["body"], json.loads(r["underline"]), json.loads(r["highlight"]))
    return {"id": f"c{r['id']}", "tag": r["tag"], "cite_short": r["cite_short"], "cite_rest": r["cite_rest"],
            "runs": runs, "origin": r["origin"]}


def search_cards(query: str, limit: int) -> list[sqlite3.Row]:
    words = re.findall(r"\w+", query.lower())
    if not words:
        return []
    where = " and ".join("lower(tag || ' ' || cite_short || ' ' || body) like ?" for _ in words)
    return db().execute(
        f"select id, tag, cite_short, substr(body, 1, 200) snippet, origin from cards where {where} "
        "order by id desc limit ?",
        [*(f"%{w}%" for w in words), limit],
    ).fetchall()
