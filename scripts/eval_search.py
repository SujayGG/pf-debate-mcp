"""Search quality check on the real library: does each plain-English question surface an on-topic card?

  uv run python scripts/eval_search.py

A hit means one of the top 5 tags contains any of the expected words. It's crude, but it catches regressions.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pf_debate_mcp import semantic  # noqa: E402

CASES = [
    ("why economic recessions make wars more likely", ["econ", "recession", "decline", "downturn"]),
    ("cards that say losing the AI race to China is dangerous", ["ai", "artificial"]),
    ("renewable energy is too expensive for poor families", ["renewable", "energy", "price", "cost"]),
    ("nuclear war would cause extinction", ["extinction", "nuclear winter", "extinct"]),
    ("climate change causes conflict and war", ["climate", "warming"]),
    ("US hegemony keeps the peace", ["heg", "primacy", "leadership", "hegemony"]),
    ("nuclear proliferation leads to war", ["prolif", "proliferation"]),
    ("data centers use too much water", ["water"]),
    ("tariffs hurt American farmers", ["tariff", "farm", "trade"]),
    ("social media harms teenagers mental health", ["social media", "mental", "teen"]),
    ("automation will cause mass unemployment", ["automation", "job", "unemploy"]),
    ("space militarization increases conflict risk", ["space", "asat", "militar"]),
    ("pandemics could cause human extinction", ["pandemic", "disease", "bioweapon", "extinction"]),
    ("sanctions don't work against Russia", ["sanction"]),
    ("universal basic income reduces poverty", ["ubi", "basic income", "poverty"]),
]


def main() -> None:
    hits, slow = 0, 0.0
    for q, words in CASES:
        t = time.time()
        tags = [r["tag"].lower() for r in semantic.hybrid_search(q, limit=5)]
        slow = max(slow, time.time() - t)
        ok = any(w in tag for tag in tags for w in words)
        hits += ok
        print(("PASS " if ok else "MISS ") + q + ("" if ok else f"\n       top: {tags[:2]}"))
    print(f"\n{hits}/{len(CASES)} on topic; slowest query {slow * 1000:.0f} ms")


if __name__ == "__main__":
    main()
