"""The card library: OpenCaselist (HF Yusuf5/OpenCaselist, MIT) in a local SQLite FTS5 index.

The dataset is ~4.8M cards across 109 parquet shards (27 GB). The build reads only the
rows/columns it needs straight from Hugging Face, one shard at a time, dedupes by
bucketId (identical cards read by different teams), and records finished shards so an
interrupted build resumes where it stopped.
"""

import re
import sqlite3
import sys
import time
import zlib

import duckdb
import httpx

from .cards import runs_from_markup
from .store import HOME

DATASET = "Yusuf5/OpenCaselist"
DB_PATH = HOME / "library.db"

_SCHEMA = """
create table if not exists cards(
  id integer primary key, bucket text unique, reads int, event text, year int, side text, caselist text,
  tag text, cite text, fullcite text, heads text, spoken text, markup blob);
create virtual table if not exists fts using fts5(
  tag, cite, heads, spoken, content='', tokenize='porter unicode61 remove_diacritics 2');
create table if not exists shards(name text primary key);
"""

_QUERY = """
select id, bucketId, try_cast(duplicateCount as int) reads, coalesce(event, 'openev') ev,
       try_cast(year as int) yr, side, caselistDisplayName, tag, cite, fullcite,
       concat_ws(' > ', pocket, hat, block) heads, spoken, markup
from read_parquet(?)
where (list_contains(?, event) or (event is null and ?))
  and (coalesce(event, '') not in ('cx', 'ld') or try_cast(duplicateCount as int) >= ?)
  and (year is null or try_cast(year as int) >= ?)
  and markup is not null and length(spoken) > 0          -- unhighlighted rows are mostly paraphrase dumps
  and length(tag) between 5 and 300 and length(cite) < 200  -- longer ones are mis-parsed docs
"""


def _connect() -> sqlite3.Connection:
    HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def _shards() -> list[str]:
    r = httpx.get(f"https://huggingface.co/api/datasets/{DATASET}/tree/main/data", timeout=30)
    r.raise_for_status()
    return sorted(f["path"] for f in r.json() if f["path"].endswith(".parquet"))


def build(events: list[str], min_reads: int, since: int, limit: int | None, log=print) -> None:
    """events: any of pf, ld, cx, openev (camp files). min_reads filters only ld/cx."""
    con = _connect()
    done = {r[0] for r in con.execute("select name from shards")}
    duck = duckdb.connect()
    duck.execute("SET enable_progress_bar=false")
    duck.execute("SET threads=4")  # more parallel range requests trip Hugging Face's 429 limit
    shards = _shards()
    inserted = con.execute("select count(*) from cards").fetchone()[0]
    for n, shard in enumerate(shards, 1):
        if shard in done:
            continue
        url = f"https://huggingface.co/datasets/{DATASET}/resolve/main/{shard}"
        params = [url, [e for e in events if e != "openev"], "openev" in events, min_reads, since]
        for attempt in range(8):
            try:
                cur = duck.execute(_QUERY, params)
                break
            except duckdb.Error as e:
                if "429" not in str(e) and attempt >= 2:
                    raise
                wait = 30 * (attempt + 1)
                log(f"  {shard}: {str(e)[:80]}... retrying in {wait}s")
                time.sleep(wait)
        else:
            raise RuntimeError(f"Gave up on {shard} after repeated rate limits; rerun to resume.")
        added = 0
        while batch := cur.fetchmany(2000):
            with con:
                for row in batch:
                    (cid, bucket, reads, ev, yr, side, caselist, tag, cite, fullcite, heads, spoken, markup) = row
                    c = con.execute(
                        "insert or ignore into cards values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, bucket, reads or 1, ev, yr, side, caselist, tag, cite, fullcite, heads,
                         (spoken or "")[:400], zlib.compress(markup.encode())),
                    )
                    if c.rowcount:
                        con.execute("insert into fts(rowid, tag, cite, heads, spoken) values (?,?,?,?,?)",
                                    (cid, tag, cite, heads, spoken or ""))
                        added += 1
            if limit and inserted + added >= limit:
                break
        inserted += added
        with con:
            con.execute("insert into shards values (?)", (shard,))
        log(f"[{n}/{len(shards)}] {shard}: +{added} cards (total {inserted})")
        if limit and inserted >= limit:
            log(f"Reached --limit {limit}.")
            break
    log("Optimizing search index...")
    con.execute("insert into fts(fts) values ('optimize')")
    con.commit()
    log(f"Done: {inserted} unique cards in {DB_PATH}")


def _ready() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    con = _connect()
    return con if con.execute("select 1 from cards limit 1").fetchone() else None


def status() -> dict:
    con = _ready()
    if not con:
        return {"built": False, "path": str(DB_PATH),
                "fix": "Run once in a terminal: uvx pf-debate-mcp build-library"}
    by_event = dict(con.execute("select event, count(*) from cards group by event").fetchall())
    lo, hi = con.execute("select min(year), max(year) from cards").fetchone()
    shards = con.execute("select count(*) from shards").fetchone()[0]
    return {"built": True, "cards": sum(by_event.values()), "by_event": by_event, "years": [lo, hi],
            "shards_done": shards, "path": str(DB_PATH), "size_mb": round(DB_PATH.stat().st_size / 1e6)}


def _match(query: str, op: str) -> str:
    return f" {op} ".join(f'"{w}"' for w in re.findall(r"\w+", query))


def search(query: str, limit: int = 10, year_from: int | None = None, side: str | None = None,
           event: str | None = None, sort: str = "relevance") -> list[dict]:
    con = _ready()
    if not con or not re.search(r"\w", query):
        return []
    filters, args = "", []
    if year_from:
        filters += " and (c.year >= ? or c.year is null)"
        args.append(year_from)
    if side:
        filters += " and upper(substr(c.side, 1, 1)) = ?"
        args.append(side[0].upper())
    if event:
        filters += " and c.event = ?"
        args.append(event.lower())
    order = "c.reads desc, score" if sort == "popular" else "score"
    sql = f"""select * from (
        select c.id, c.tag, c.cite, c.year, c.event, c.side, c.reads, c.heads, c.spoken,
               bm25(fts, 8.0, 2.0, 3.0, 1.0) score
        from fts join cards c on c.id = fts.rowid where fts match ? {filters}
        order by score limit 300) c order by {order} limit ?"""
    for op in ("AND", "OR"):  # all words first; fall back to any word
        rows = con.execute(sql, [_match(query, op), *args, limit]).fetchall()
        if rows:
            break
    return [{"id": f"lib:{r['id']}", "tag": r["tag"], "cite": r["cite"], "year": r["year"],
             "event": r["event"], "side": r["side"], "times_read": r["reads"], "headings": r["heads"],
             "highlighted": (r["spoken"] or "")[:240]} for r in rows]


def get(card_id: int) -> dict | None:
    con = _ready()
    r = con and con.execute("select * from cards where id=?", (card_id,)).fetchone()
    if not r:
        return None
    full, short = r["fullcite"] or "", r["cite"] or ""
    rest = full[len(short):].strip() if full.startswith(short) else full
    return {"id": f"lib:{r['id']}", "tag": r["tag"], "cite_short": short, "cite_rest": rest,
            "runs": runs_from_markup(zlib.decompress(r["markup"]).decode()),
            "origin": f"OpenCaselist {r['event']} {r['caselist'] or ''} {r['year'] or ''}".strip(),
            "headings": r["heads"], "times_read": r["reads"]}


if __name__ == "__main__":  # quick manual check: python -m pf_debate_mcp.library "query"
    for hit in search(" ".join(sys.argv[1:]) or "nuclear war"):
        print(hit)
