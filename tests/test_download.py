"""Prebuilt library install: resume, checksum, version pointer, and swapping while a connection is open."""

import gzip
import hashlib
import json
import sqlite3

import pytest

from pf_debate_mcp import library

from conftest import PAGES


def publish(version: int, cards: list[str], schema: int = library.SCHEMA_VERSION) -> bytes:
    """Serve a tiny library-v{version}.db.gz plus manifest.json from the test web server."""
    path = library.HOME / f"_src-v{version}.db"
    path.unlink(missing_ok=True)
    con = library._connect(path)
    for i, tag in enumerate(cards, 1):
        con.execute("insert into cards(id, bucket, reads, event, tag, cite, markup) values (?,?,?,?,?,?,?)",
                    (i, f"b{i}", 1, "pf", tag, "Cite 25", b""))
        con.execute("insert into fts(rowid, tag, cite, heads, spoken) values (?,?,?,?,?)", (i, tag, "", "", ""))
    con.execute(f"pragma user_version={schema}")
    con.commit()
    con.close()
    blob = gzip.compress(path.read_bytes())
    PAGES[f"/lib/library-v{version}.db.gz"] = ("application/gzip", blob)
    PAGES["/lib/manifest.json"] = ("application/json", json.dumps({
        "version": version, "schema": schema, "file": f"library-v{version}.db.gz", "size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "cards": len(cards)}).encode())
    return blob


@pytest.fixture
def prebuilt(web, monkeypatch):
    monkeypatch.setattr(library, "PREBUILT", f"{web}/lib")
    library.POINTER.unlink(missing_ok=True)
    yield
    library.POINTER.unlink(missing_ok=True)  # later tests use the from-source tiny_library


def test_download_installs_and_points(prebuilt):
    publish(1, ["Solar subsidies create jobs"])
    library.download(log=lambda m: None)
    assert library.db_path().name == "library-v1.db"
    assert library.search("solar jobs")[0]["tag"] == "Solar subsidies create jobs"


def test_resume_from_partial_file(prebuilt):
    blob = publish(2, ["Tariffs raise consumer prices"])
    (library.HOME / "library-v2.db.gz.part").write_bytes(blob[:100])  # an earlier interrupted download
    library.download(log=lambda m: None)
    assert library.db_path().name == "library-v2.db"


def test_bad_checksum_keeps_old_library(prebuilt):
    publish(3, ["First"])
    library.download(log=lambda m: None)
    blob = publish(4, ["Second"])
    PAGES["/lib/library-v4.db.gz"] = ("application/gzip", blob[:-10] + b"corrupted!")
    with pytest.raises(RuntimeError, match="checksum"):
        library.download(log=lambda m: None)
    assert library.db_path().name == "library-v3.db"
    assert not (library.HOME / "library-v4.db.gz.part").exists()


def test_swap_while_connection_open(prebuilt):
    publish(5, ["Old card about nuclear power"])
    library.download(log=lambda m: None)
    held = sqlite3.connect(library.db_path())  # e.g. Claude Desktop's server has the old file open
    held.execute("select 1").fetchone()
    publish(6, ["New card about wind power"])
    library.download(log=lambda m: None)  # must not try to replace or delete-fail on the open file
    assert library.db_path().name == "library-v6.db"
    assert library.search("wind power")[0]["tag"] == "New card about wind power"
    held.close()


def test_newer_schema_is_refused(prebuilt):
    publish(7, ["Future card"], schema=library.SCHEMA_VERSION + 1)
    with pytest.raises(RuntimeError, match="newer pf-debate-mcp"):
        library.download(log=lambda m: None)
