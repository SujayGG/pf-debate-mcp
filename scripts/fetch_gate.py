"""Fetch-success gate: how often can a datacenter server fetch the sources debaters actually cite?

Samples cite URLs from recent PF cards in the library and fetches each with the hosted-mode guard.
audit_evidence ships on the hosted server only if this rate is acceptable (docs/roadmap.md, T14).

  uv run python scripts/fetch_gate.py --n 50        # run from a datacenter (GitHub Actions / the Space)
"""

import argparse
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pf_debate_mcp import library  # noqa: E402
from pf_debate_mcp.sources import FetchError, fetch  # noqa: E402

URL = re.compile(r"https?://[^\s\]\)\"'>,;]+")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--since", type=int, default=2020)
    args = ap.parse_args()
    con = library._ready()
    if not con:
        sys.exit("No library installed. Run: pf-debate-mcp build-library")
    rows = con.execute("select fullcite from cards where event='pf' and year >= ? and fullcite like '%http%'",
                       (args.since,)).fetchall()
    urls = sorted({m.group().rstrip(".") for (c,) in rows for m in URL.finditer(c)})
    random.seed(7)
    sample = random.sample(urls, min(args.n, len(urls)))
    results = Counter()
    for u in sample:
        try:
            fetch(u, block_private=True)
            results["ok"] += 1
            print("ok     ", u)
        except FetchError as e:
            kind = "paywall/short" if "characters extracted" in str(e) else \
                   "http error" if "HTTP" in str(e) else "unreachable/other"
            results[kind] += 1
            print(f"{kind:14}", u)
    total = sum(results.values())
    print(f"\n{results['ok']}/{total} fetched ({100 * results['ok'] // max(total, 1)}%). Failures: "
          + ", ".join(f"{k} {v}" for k, v in results.items() if k != "ok"))


if __name__ == "__main__":
    main()
