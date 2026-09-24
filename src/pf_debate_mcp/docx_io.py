"""Verbatim-compatible .docx export and parsing.

Verbatim (the standard debate Word template) maps Pocket/Hat/Block/Tag onto Word's
Heading 1-4, so plain Heading styles open correctly in Verbatim and in plain Word.
"""

import io
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.shared import Pt, RGBColor

from .cards import Run, normalize_runs

_HEADINGS = {"pocket": (1, 26), "hat": (2, 22), "block": (3, 16), "tag": (4, 13)}


def _style_doc(doc) -> None:
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    for level, size in _HEADINGS.values():
        st = doc.styles[f"Heading {level}"]
        st.font.size, st.font.bold, st.font.name = Pt(size), True, "Calibri"
        st.font.color.rgb = RGBColor(0, 0, 0)
        if level <= 2:
            st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Speech prose between cards gets its own style so parse() never folds it into a card body.
    doc.styles.add_style("Analytic", WD_STYLE_TYPE.PARAGRAPH).base_style = doc.styles["Normal"]


def export(title: str, items: list[dict], path: Path) -> Path:
    """items: {"pocket"|"hat"|"block"|"tag": str} | {"text": str} | {"card": card dict}."""
    doc = Document()
    _style_doc(doc)
    doc.core_properties.title = title
    for item in items:
        if "card" in item:
            c = item["card"]
            doc.add_heading(c["tag"], 4)
            p = doc.add_paragraph()
            short = p.add_run(c["cite_short"])
            short.bold, short.font.size = True, Pt(13)
            p.add_run(" " + (c.get("cite_rest") or "")).font.size = Pt(8)
            p = doc.add_paragraph()
            for text, u, h in c["runs"]:
                if text == "\n":
                    p = doc.add_paragraph()
                    continue
                r = p.add_run(text)
                if u or h:
                    r.underline = True
                else:
                    r.font.size = Pt(8)  # unread text is shrunk, the Verbatim convention
                if h:
                    r.font.highlight_color = WD_COLOR_INDEX.TURQUOISE
        elif "text" in item:
            doc.add_paragraph(item["text"], style="Analytic")
        else:
            (kind, text), = item.items()
            doc.add_heading(text, _HEADINGS[kind][0])
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def _level(paragraph) -> str | None:
    name = (paragraph.style.name or "").lower()
    for key, (level, _) in _HEADINGS.items():
        if name == f"heading {level}" or key in name:
            return key
    return None


def parse(data: bytes) -> list[dict]:
    """Split a Verbatim-style speech doc into cards with their pocket/hat/block context."""
    doc = Document(io.BytesIO(data))
    ctx = {"pocket": None, "hat": None, "block": None}
    cards, cur = [], None
    for p in doc.paragraphs:
        level = _level(p)
        if level and level != "tag":
            ctx[level] = p.text.strip()
            if level == "pocket":
                ctx["hat"] = ctx["block"] = None
            elif level == "hat":
                ctx["block"] = None
            cur = None
            continue
        if (p.style.name or "").lower() == "analytic":
            cur = None
            continue
        if level == "tag":
            cur = {**ctx, "tag": p.text.strip(), "cite_short": None, "cite_rest": "", "runs": []}
            cards.append(cur)
            continue
        if cur is None or not p.text.strip():
            continue
        if cur["cite_short"] is None:
            bold = "".join(r.text for r in p.runs if r.bold).strip()
            cur["cite_short"] = bold or p.text.strip()[:40]
            cur["cite_rest"] = p.text.strip()[len(bold):].strip() if bold else p.text.strip()
            continue
        if cur["runs"]:
            cur["runs"].append(("\n", False, False))
        for r in p.runs:
            sname = (r.style.name or "").lower() if r.style is not None else ""
            u = bool(r.underline) or "underline" in sname or "emphasis" in sname
            h = r.font.highlight_color is not None
            cur["runs"].append((r.text, u, h))
    out = []
    for c in cards:
        if c["runs"]:
            c["runs"] = normalize_runs(c["runs"])
            out.append(c)
    return out
