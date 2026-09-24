"""Card cutting: the evidence-ethics gate.

A card body is always an exact slice of the source text. Quotes the agent passes in
are only matched after normalizing whitespace, quote marks and dashes; anything else
that differs from the source is rejected, so a card can never contain invented text.
"""

import re
from datetime import date
from html.parser import HTMLParser

Run = tuple[str, bool, bool]  # (text, underlined, highlighted)

_TRANS = {
    "‘": "'", "’": "'", "‚": "'", "′": "'", "`": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-",
}


class CutError(ValueError):
    pass


def _norm(s: str) -> tuple[str, list[int]]:
    """Normalized text plus, for each normalized char, its index in the original."""
    out, idx, prev_space = [], [], False
    for i, ch in enumerate(s):
        ch = _TRANS.get(ch, ch)
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        out.append(ch)
        idx.append(i)
    return "".join(out), idx


def _hint(haystack: str, needle: str) -> str:
    words = needle.split(" ")
    for k in range(len(words) - 1, 0, -1):
        prefix = " ".join(words[:k])
        if prefix in haystack:
            return f" The source matches only up to: '{prefix}' — the next words differ."
    return " Not even the first word matched; re-read the source text."


def _find(text: str, quote: str, what: str, frm: int = 0) -> tuple[int, int]:
    """Locate quote in text (searching from normalized offset frm); return original (start, end)."""
    tn, ti = _norm(text)
    qn = _norm(quote.strip())[0]
    if not qn:
        raise CutError(f"{what} is empty.")
    pos = tn.find(qn, frm)
    if pos < 0 and frm:
        pos = tn.find(qn)
    if pos < 0:
        raise CutError(f"{what} not found verbatim: '{quote[:120]}'.{_hint(tn, qn)}")
    return ti[pos], ti[pos + len(qn) - 1] + 1


def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _marks(body: str, quotes: list[str], what: str) -> list[tuple[int, int]]:
    ranges, cursor = [], 0
    for q in quotes:
        try:
            s, e = _find(body, q, f"{what} '{q[:60]}'", cursor)
        except CutError as err:
            raise CutError(f"{err} It must be copied exactly from inside the card body.") from None
        ranges.append((s, e))
        cursor = len(_norm(body[:e])[0])
    return ranges


def cut(text: str, start_quote: str, end_quote: str, underline: list[str], highlight: list[str]) -> dict:
    """Cut a card from source text. Raises CutError when anything is not verbatim."""
    if not highlight:
        raise CutError("A card needs at least one highlight (the words read aloud).")
    s, _ = _find(text, start_quote, "start_quote")
    _, e = _find(text, end_quote, "end_quote", frm=len(_norm(text[:s])[0]))
    if e <= s:
        raise CutError("end_quote occurs before start_quote in the source.")
    body = text[s:e]
    hl = _marks(body, highlight, "highlight")
    ul = _marks(body, underline, "underline") if underline else list(hl)
    ul, hl = _merge(ul), _merge(hl)

    warnings = []
    for hs, he in hl:
        if not any(us <= hs and he <= ue for us, ue in ul):
            warnings.append(f"highlight '{body[hs:he][:60]}' is not underlined")
    if len(re.findall(r"[.!?](\s|$)", body)) < 2:
        warnings.append("body is under 2 sentences; include enough context that the author's meaning is clear")
    read = sum(e - s for s, e in hl)
    if read > 0.6 * len(body):
        warnings.append("over 60% highlighted; cut tighter so the card reads fast")
    return {"body": body, "underline": ul, "highlight": hl, "warnings": warnings}


def runs_from_ranges(body: str, underline, highlight) -> list[Run]:
    cuts = sorted({0, len(body), *[p for r in (*underline, *highlight) for p in r]})
    runs: list[Run] = []
    for a, b in zip(cuts, cuts[1:]):
        u = any(s <= a and b <= e for s, e in underline)
        h = any(s <= a and b <= e for s, e in highlight)
        if runs and runs[-1][1:] == (u, h):
            runs[-1] = (runs[-1][0] + body[a:b], u, h)
        elif b > a:
            runs.append((body[a:b], u, h))
    return runs


def ranges_from_runs(runs: list[Run]) -> tuple[str, list, list]:
    body, ul, hl, pos = "", [], [], 0
    for text, u, h in runs:
        if u:
            ul.append((pos, pos + len(text)))
        if h:
            hl.append((pos, pos + len(text)))
        body += text
        pos += len(text)
    return body, _merge(ul), _merge(hl)


def render(card: dict) -> str:
    """Plain-text view for agents: ==highlighted== (read aloud), _underlined_ (context)."""
    segs: list[list[str]] = []  # [kind, text]; highlight wins over underline for display
    for text, u, h in card["runs"]:
        kind = "==" if h else "_" if u else ""
        if segs and segs[-1][0] == kind:
            segs[-1][1] += text
        else:
            segs.append([kind, text])
    body = [f"{k}{t}{k}" for k, t in segs]
    return f"[{card['id']}] {card['tag']}\n{card['cite_short']} {card['cite_rest']}\n{''.join(body)}"


def format_cite(c: dict) -> tuple[str, str, list[str]]:
    """Return (short cite, bracketed full cite, warnings) per NSDA citation rules."""
    author = (c.get("author") or "").strip()
    publisher = (c.get("publisher") or "").strip()
    d = (c.get("date") or "").strip()
    warnings = []
    if not author and not publisher:
        warnings.append("no author or publisher: NSDA requires an author (use the organization if no person)")
    if not d:
        warnings.append("no date: NSDA requires a publication date; use 'n.d.' only if truly undated")
    if not c.get("quals"):
        warnings.append("no author qualifications: add them (judges and opponents check quals)")
    if not c.get("url"):
        warnings.append("no URL: the source must be retrievable")
    name = author or publisher or "Unknown"
    first = re.split(r",| and | & |;", name)[0].strip()
    last = first.split()[-1] if 0 < len(first.split()) <= 3 else first
    if len(re.split(r",| and | & |;", name)) > 1 and author:
        last += " et al."
    year = re.search(r"(19|20)(\d{2})", d)
    short = f"{last} {year.group(2) if year else 'n.d.'}"
    title = c.get("title")
    parts = [
        author,
        c.get("quals"),
        f'"{title}"' if title else None,
        publisher,
        d,
        c.get("url"),
        f"accessed {c.get('accessed') or date.today().isoformat()}",
    ]
    return short, "[" + "; ".join(p for p in parts if p) + "]", warnings


class _MarkupParser(HTMLParser):
    """Dataset markup: <h4>tag</h4><p>cite</p><p>body with <u>, <mark>, <strong>...</p>."""

    def __init__(self):
        super().__init__()
        self.depth = {"u": 0, "mark": 0}
        self.paras: list[list[Run]] = []
        self.in_h4 = False

    def handle_starttag(self, tag, attrs):
        if tag in self.depth:
            self.depth[tag] += 1
        elif tag == "p":
            self.paras.append([])
        elif tag == "h4":
            self.in_h4 = True

    def handle_endtag(self, tag):
        if tag in self.depth:
            self.depth[tag] = max(0, self.depth[tag] - 1)
        elif tag == "h4":
            self.in_h4 = False

    def handle_data(self, data):
        if self.in_h4 or not self.paras:
            return
        self.paras[-1].append((data, self.depth["u"] > 0, self.depth["mark"] > 0))


def runs_from_markup(markup: str) -> list[Run]:
    p = _MarkupParser()
    p.feed(markup or "")
    body = p.paras[1:]  # first <p> is the cite
    runs: list[Run] = []
    for i, para in enumerate(body):
        runs.extend(para)
        if i < len(body) - 1:
            runs.append(("\n", False, False))
    return normalize_runs(runs)


def normalize_runs(runs: list[Run]) -> list[Run]:
    """Normalize a run list (merge neighbours with equal formatting)."""
    body, ul, hl = ranges_from_runs(runs)
    return runs_from_ranges(body, ul, hl)
