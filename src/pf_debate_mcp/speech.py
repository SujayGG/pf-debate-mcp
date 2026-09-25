"""What a debater actually says aloud, and how long it takes: counted exactly, no AI.

A card is read as its tag, its short cite, and only its highlighted words (underlined words if nothing is
highlighted; the whole body if the card is unmarked). Hat and block headings count as spoken signposts;
pockets ("Aff", "Neg Blocks") are file labels and don't. Timing = words / wpm.
"""

from .cards import Run

SPEECHES = {"constructive": 240, "rebuttal": 240, "summary": 180, "final focus": 120}
LEVEL = {"pocket": 1, "hat": 2, "block": 3}


def words(s: str) -> int:
    return sum(1 for w in s.split() if any(ch.isalnum() for ch in w))


def clock(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60}:{s % 60:02d}"


def read_runs(runs: list[Run]) -> list[Run]:
    """The runs read aloud, with a plain space wherever skipped text sat between two read runs."""
    key = 2 if any(r[2] for r in runs) else 1 if any(r[1] for r in runs) else None
    if key is None:
        return list(runs)
    out: list[Run] = []
    gap = False
    for r in runs:
        if not r[key]:
            gap = True
            continue
        if gap and out and not out[-1][0][-1:].isspace() and not r[0][:1].isspace():
            out.append((" ", False, False))
        out.append(r)
        gap = False
    return out


def read_text(card: dict) -> str:
    return " ".join("".join(t for t, _, _ in read_runs(card["runs"])).split())


def script(items: list[dict]) -> list[tuple[str, str, int]]:
    """(kind, spoken text, word count) in reading order. items: resolved export items (card dicts inline)."""
    out = []
    for it in items:
        if "card" in it:
            c = it["card"]
            out.append(("tag", c["tag"], words(c["tag"])))
            body = f"{c['cite_short']}: {read_text(c)}"
            out.append(("card", body, words(body)))
        else:
            (kind, text), = it.items()
            out.append((kind, text, 0 if kind == "pocket" else words(text)))
    return out


def section_words(lines: list[tuple[str, str, int]]) -> dict[int, int]:
    """{index of a hat/block heading: words spoken under it (up to the next heading at its level or above)}."""
    out = {}
    for i, (kind, _, _) in enumerate(lines):
        if kind not in ("hat", "block"):
            continue
        total = 0
        for k, _, n in lines[i + 1:]:
            if k in LEVEL and LEVEL[k] <= LEVEL[kind]:
                break
            total += n
        out[i] = total
    return out


def check_wpm(wpm: int) -> None:
    if not 80 <= wpm <= 400:
        raise ValueError("wpm must be between 80 and 400 (lay about 160, fast about 200, circuit about 230+)")


def report(items: list[dict], speech: str, wpm: int) -> str:
    """Timing summary, per-section times, cut candidates when over, then the read-ready script."""
    if speech not in SPEECHES:
        raise ValueError(f"speech must be one of: {', '.join(SPEECHES)}")
    check_wpm(wpm)
    lines = script(items)
    total = sum(n for _, _, n in lines)
    secs, limit = total / wpm * 60, SPEECHES[speech]
    diff = secs - limit
    if diff > 0:
        verdict = f"{clock(diff)} OVER: cut about {round(diff * wpm / 60)} words"
    elif diff < -15:
        verdict = f"{clock(-diff)} under: room for about {round(-diff * wpm / 60)} more words"
    else:
        verdict = "fits"
    out = [f"{speech.title()}: {clock(secs)} of {clock(limit)} at {wpm} wpm ({total} words). {verdict}."]
    for i, n in section_words(lines).items():
        indent = "  " if lines[i][0] == "hat" else "    "
        out.append(f"{indent}{lines[i][1]}: {clock(n / wpm * 60)} ({n} words)")
    if diff > 0:
        cards = sorted(((n, lines[i - 1][1]) for i, (k, _, n) in enumerate(lines) if k == "card"), reverse=True)
        if cards:
            out.append("Longest cards (trim highlighting here first; re-cut, never paraphrase):")
            out += [f"  {n} words: {tag}" for n, tag in cards[:3]]
    out.append("\n--- Read-ready script ---")
    for kind, text, _ in lines:
        if kind != "pocket":
            out.append(f"\n{text}" if kind in ("hat", "block") else text)
    return "\n".join(out)
