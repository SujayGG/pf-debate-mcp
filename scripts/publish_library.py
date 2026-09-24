"""Package the local library for download and (optionally) upload it to Hugging Face.

  uv run python scripts/publish_library.py --version 1            # writes dist/library/
  uv run python scripts/publish_library.py --version 1 --upload   # also uploads (needs `hf auth login`)

Output: library-v{N}.db.gz, manifest.json (version, schema, size, sha256, cards), README.md (dataset card).
"""

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pf_debate_mcp import library  # noqa: E402

REPO = "SujayG5/pf-debate-library"
OUT = Path(__file__).resolve().parent.parent / "dist" / "library"

CARD = """---
license: mit
pretty_name: pf-debate library
tags: [debate, argument-mining, public-forum]
---
# pf-debate library

Prebuilt SQLite FTS5 card library used by [pf-debate-mcp](https://github.com/SujayGG/pf-debate-mcp).
It is built from the [OpenCaselist dataset](https://huggingface.co/datasets/Yusuf5/OpenCaselist) (MIT),
evidence disclosed by the debate community on openCaselist, and is deduplicated by bucket.
It contains every PF and OpenEv card that passed the quality filters, plus LD/Policy cards read by 5 or more teams.

Download it with `pf-debate-mcp build-library` or the `build_library` tool; don't fetch it by hand.
Card text belongs to its original authors; cites are kept as disclosed.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--source", type=Path, default=None, help="library file (default: the active one)")
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()

    src = args.source or library.db_path()
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    db = OUT / f"library-v{args.version}.db"
    print(f"Snapshotting {src}...")
    # closing() because sqlite3's own context manager commits but never closes (Windows then locks the file)
    with closing(sqlite3.connect(src)) as a, closing(sqlite3.connect(db)) as b:
        a.backup(b)  # consistent copy even if the source is in WAL mode
    with closing(sqlite3.connect(db)) as con:
        con.execute(f"pragma user_version={library.SCHEMA_VERSION}")
        con.execute("pragma journal_mode=delete")  # a single self-contained file
        cards = con.execute("select count(*) from cards").fetchone()[0]
        con.execute("vacuum")

    gz = db.with_name(db.name + ".gz")
    print(f"Compressing {db.stat().st_size // 1_000_000} MB...")
    with open(db, "rb") as f, gzip.open(gz, "wb", compresslevel=6) as g:
        shutil.copyfileobj(f, g, 1 << 20)
    db.unlink()
    digest = hashlib.sha256(gz.read_bytes()).hexdigest()
    manifest = {"version": args.version, "schema": library.SCHEMA_VERSION, "file": gz.name,
                "size": gz.stat().st_size, "sha256": digest, "cards": cards, "built": date.today().isoformat(),
                "source": "Yusuf5/OpenCaselist (MIT)"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (OUT / "README.md").write_text(CARD, encoding="utf-8")
    print(json.dumps(manifest, indent=2))

    if args.upload:
        cmd = ["uvx", "--from", "huggingface_hub", "hf", "upload", REPO, str(OUT), ".", "--repo-type", "dataset",
               "--commit-message", f"library v{args.version}"]
        subprocess.run(cmd, check=True, shell=sys.platform == "win32")


if __name__ == "__main__":
    main()
