"""The card library: OpenCaselist (HF Yusuf5/OpenCaselist, MIT) in a local SQLite FTS5 index.

The dataset is ~4.8M cards across 109 parquet shards (27 GB). The build reads only the
rows/columns it needs straight from Hugging Face, one shard at a time, dedupes by
bucketId (identical cards read by different teams), and records finished shards so an
interrupted build resumes where it stopped.

Most users never build: download() fetches the prebuilt library published on Hugging Face.

  current.txt ──names──▶ library-v{N}.db (downloaded)  or  library.db (built from source)

A new version always lands under a new file name and only then does current.txt switch to it,
so nothing ever replaces a file another connection has open (Windows forbids that).
"""

import gzip
import hashlib
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import zlib
from pathlib import Path

import duckdb
import httpx

from .cards import runs_from_markup
from .store import HOME

DATASET = "Yusuf5/OpenCaselist"
PREBUILT = "https://huggingface.co/datasets/SujayG5/pf-debate-library/resolve/main"
SCHEMA_VERSION = 1  # bump when the cards/fts layout changes; stored as sqlite user_version
SOURCE_DB = HOME / "library.db"  # where from-source builds write
POINTER = HOME / "current.txt"
PRESETS = {  # (events, min_reads for ld/cx, since year)
    "quick": (["pf"], 5, 2014),
    "full": (["pf", "openev", "ld", "cx"], 5, 2014),
}
_build = {"running": False, "last": None}  # in-process background build (the build_library tool)

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
  and markup is not null
  and (length(spoken) > 0 or event = 'pf')  -- unmarked LD/Policy rows are junk; unmarked PF cards are read in full
  and length(tag) between 5 and 300 and length(cite) < 200  -- longer ones are mis-parsed docs
"""


def db_path() -> Path:
    """The active library file: whatever current.txt names, else the from-source build."""
    try:
        active = HOME / POINTER.read_text(encoding="utf-8").strip()
    except OSError:
        return SOURCE_DB
    return active if active.is_file() else SOURCE_DB


def _point(name: str) -> None:
    tmp = POINTER.with_suffix(".tmp")
    tmp.write_text(name, encoding="utf-8")
    os.replace(tmp, POINTER)  # current.txt is never held open, so this is safe on Windows too


def _cleanup() -> None:
    """Delete library versions that are no longer active. A file still open elsewhere is kept for next time."""
    keep = db_path()
    for f in HOME.glob("library-v*.db"):
        if f != keep:
            try:
                f.unlink()
            except OSError:
                pass


def _connect(path: Path | None = None) -> sqlite3.Connection:
    HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path or db_path(), timeout=60)  # a build may be writing
    con.row_factory = sqlite3.Row
    con.execute("pragma journal_mode=wal")  # readers never block the background build (and vice versa)
    con.executescript(_SCHEMA)
    return con


_local = threading.local()  # one reader connection per thread: MCP tools run in a thread pool


def _conn() -> sqlite3.Connection | None:
    path = db_path()
    con = getattr(_local, "con", None)
    if con is not None and _local.path != path:  # a new version was installed: reopen
        con.close()
        con = _local.con = None
    if con is None and path.exists():
        con = _local.con = _connect(path)
        _local.path = path
    return con


def _shards() -> list[str]:
    r = httpx.get(f"https://huggingface.co/api/datasets/{DATASET}/tree/main/data", timeout=30)
    r.raise_for_status()
    return sorted(f["path"] for f in r.json() if f["path"].endswith(".parquet"))


def build(events: list[str], min_reads: int, since: int, limit: int | None, log=print) -> None:
    """events: any of pf, ld, cx, openev (camp files). min_reads filters only ld/cx."""
    con = _connect(SOURCE_DB)
    con.execute(f"pragma user_version={SCHEMA_VERSION}")
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
    _point(SOURCE_DB.name)
    log(f"Done: {inserted} unique cards in {SOURCE_DB}")


def download(log=print) -> None:
    """Install the prebuilt library: resumable, checksum-verified, switched in only when complete."""
    manifest = _get(f"{PREBUILT}/manifest.json").json()
    if manifest["schema"] > SCHEMA_VERSION:
        raise RuntimeError("The published library needs a newer pf-debate-mcp. Update the app, then try again.")
    target = HOME / f"library-v{manifest['version']}.db"
    if db_path() == target:
        log(f"Already up to date ({target.name}).")
        return
    HOME.mkdir(parents=True, exist_ok=True)
    part = HOME / (manifest["file"] + ".part")
    for attempt in range(6):
        have = part.stat().st_size if part.exists() else 0
        if have >= manifest["size"]:
            break
        try:
            _fetch_range(f"{PREBUILT}/{manifest['file']}", part, have, manifest["size"], log)
        except (httpx.HTTPError, OSError) as e:
            log(f"Download interrupted ({type(e).__name__}); resuming in {5 * (attempt + 1)} s...")
            time.sleep(5 * (attempt + 1))
    digest = hashlib.sha256()
    with open(part, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    if digest.hexdigest() != manifest["sha256"]:
        part.unlink()
        raise RuntimeError("Downloaded library failed its checksum and was deleted. Run build_library again.")
    log("Unpacking...")
    tmp = target.with_name(target.name + ".tmp")
    with gzip.open(part, "rb") as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    os.replace(tmp, target)  # a brand-new name: nothing has it open
    _point(target.name)
    part.unlink()
    _cleanup()
    log(f"Done: library v{manifest['version']} installed ({manifest.get('cards', '?')} cards).")


def _get(url: str) -> httpx.Response:
    r = httpx.get(url, follow_redirects=True, timeout=30)
    r.raise_for_status()
    return r


def _fetch_range(url: str, part: Path, have: int, total: int, log) -> None:
    headers = {"Range": f"bytes={have}-"} if have else {}
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        if have and r.status_code != 206:  # server ignored the range: start over
            have = 0
        with open(part, "ab" if have else "wb") as f:
            next_log = have + total // 20
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                have += len(chunk)
                if have >= next_log:
                    log(f"Downloading library: {have * 100 // total}% of {total // 1_000_000} MB")
                    next_log += total // 20


def start_background_build(mode: str) -> str:
    """Install or build the library in a thread so chat apps never need a terminal."""
    if _build["running"]:
        return f"Already running: {_build['last']}"

    def run():
        _build.update(running=True, last="starting")
        log = lambda m: _build.update(last=m)  # noqa: E731
        try:
            if mode == "download":
                download(log=log)
            else:
                build(*PRESETS[mode], None, log=log)
        except Exception as e:  # surfaced through status(); rerunning resumes
            _build["last"] = f"FAILED: {e}. Run build_library again to resume."
        finally:
            _build["running"] = False

    threading.Thread(target=run, daemon=True).start()
    what = "download of the prebuilt library" if mode == "download" else f"{mode} build from source"
    return (f"Started the {what} in the background. "
            "Check progress with library_status. Search works on whatever is built so far. If the app "
            "closes mid-build, run build_library again and it resumes.")


def _ready() -> sqlite3.Connection | None:
    con = _conn()
    if not con or con.execute("pragma user_version").fetchone()[0] > SCHEMA_VERSION:
        return None  # missing, or made by a newer app version this code can't read
    return con if con.execute("select 1 from cards limit 1").fetchone() else None


def ready() -> bool:
    """Cheap (about 1 ms) check that the library has cards. Search must use this, never status()."""
    return _ready() is not None


_status_cache: dict = {"at": 0.0, "value": None}


def status() -> dict:
    build_info = {"build_running": _build["running"], "build_progress": _build["last"]} if _build["last"] else {}
    con = _ready()
    if not con:
        return {"built": False, "path": str(db_path()), **build_info,
                "fix": "Call the build_library tool (or run `pf-debate-mcp build-library` in a terminal). "
                       "If a library exists but won't open, update pf-debate-mcp."}
    if _build["running"] or time.time() - _status_cache["at"] > 60:  # full counts take ~1 s on 173k cards
        by_event = dict(con.execute("select event, count(*) from cards group by event").fetchall())
        lo, hi = con.execute("select min(year), max(year) from cards").fetchone()
        shards = con.execute("select count(*) from shards").fetchone()[0]
        _status_cache.update(at=time.time(), value={
            "built": True, "cards": sum(by_event.values()), "by_event": by_event, "years": [lo, hi],
            "shards_done": shards, "path": str(db_path()), "size_mb": round(db_path().stat().st_size / 1e6)})
    return {**_status_cache["value"], **build_info}


def _match(query: str, op: str) -> str:
    return f" {op} ".join(f'"{w}"' for w in re.findall(r"\w+", query))


def search(query: str, limit: int = 10, year_from: int | None = None, side: str | None = None,
           event: str | None = None, sort: str = "relevance", strict: bool = False) -> list[dict]:
    """Keyword search. strict=True: all words must match (no any-word fallback)."""
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
    order = "c.reads desc, h.score" if sort == "popular" else "h.score"
    # Rank inside FTS first, then join the top hits (joining before ranking doubled query time).
    sql = f"""with hits as (select rowid id, bm25(fts, 8.0, 2.0, 3.0, 1.0) score from fts
                            where fts match ? order by score limit 1000)
        select c.id, c.tag, c.cite, c.year, c.event, c.side, c.reads, c.heads, c.spoken, h.score
        from hits h join cards c on c.id = h.id where 1=1 {filters}
        order by {order} limit ?"""
    for op in ("AND",) if strict else ("AND", "OR"):  # all words first; fall back to any word
        rows = con.execute(sql, [_match(query, op), *args, limit]).fetchall()
        if rows:
            break
    return [_row_dict(r) for r in rows]


def _row_dict(r) -> dict:
    return {"id": f"lib:{r['id']}", "tag": r["tag"], "cite": r["cite"], "year": r["year"],
            "event": r["event"], "side": r["side"], "times_read": r["reads"], "headings": r["heads"],
            "highlighted": (r["spoken"] or "")[:240]}


def rows(card_ids: list[str], year_from: int | None = None, side: str | None = None,
         event: str | None = None) -> list[dict]:
    """Search-result rows for lib:N ids, applying the same filters as search()."""
    con = _ready()
    ids = [int(c[4:]) for c in card_ids if c.startswith("lib:")]
    if not con or not ids:
        return []
    sql = f"select * from cards c where c.id in ({','.join('?' * len(ids))})"
    args: list = list(ids)
    if year_from:
        sql += " and (c.year >= ? or c.year is null)"
        args.append(year_from)
    if side:
        sql += " and upper(substr(c.side, 1, 1)) = ?"
        args.append(side[0].upper())
    if event:
        sql += " and c.event = ?"
        args.append(event.lower())
    return [_row_dict(r) for r in con.execute(sql, args).fetchall()]


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
