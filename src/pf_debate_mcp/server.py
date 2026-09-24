"""pf-debate MCP server: tools for a Public Forum debate partner.

The host agent does the thinking (strategy, writing, choosing evidence); these tools give
it the card library, clean source text, a verbatim-only card cutter, caselist access, and
Verbatim-style .docx output. Skills in ./skills are also served as prompts and resources.
"""

import re
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import caselist as cl
from . import library, store
from .cards import CutError, cut, format_cite, ranges_from_runs, render, render_read
from .docx_io import export, export_html, parse
from .sources import FetchError, fetch, paragraphs

SKILLS = Path(__file__).parent / "skills"

INSTRUCTIONS = """You are a Public Forum (PF) debate partner. Before PF work, call pf_guide("pf-debate")
and then the guides it points to (jargon, format, tactics, impacts, and the task guides pf-case,
pf-cut-card, pf-analyze, pf-blocks, pf-scout). Evidence rules are non-negotiable: never write card text from memory; every
card comes from search_cards/get_card (existing cards) or fetch_source + cut_card (new cards), and
cut_card only accepts text that appears verbatim in the source. Use your own web search to find URLs.
IDs: lib:N = library card, cN = user's card, sN = fetched source."""

mcp = MCPServer("pf-debate", instructions=INSTRUCTIONS)


def _card(card_id: str) -> dict:
    card_id = card_id.strip()
    if m := re.fullmatch(r"lib:(\d+)", card_id):
        card = library.get(int(m[1]))
    elif m := re.fullmatch(r"c(\d+)", card_id):
        card = store.get_card(int(m[1]))
    else:
        raise ToolError(f"Unknown card id '{card_id}' (expected lib:N or cN).")
    if not card:
        raise ToolError(f"Card {card_id} not found. Use search_cards (scope='mine' for your own cuts).")
    return card


@mcp.tool()
def search_cards(query: str, scope: str = "library", year_from: int | None = None, side: str | None = None,
                 event: str | None = None, sort: str = "relevance", limit: int = 10) -> list[dict]:
    """Search already-cut debate cards by keywords.

    scope: "library" = OpenCaselist corpus (PF, LD, Policy, camp OpenEv files; 2014-2022);
           "mine" = cards the user cut or imported.
    sort: "relevance" or "popular" (most-read by teams first; a strong quality signal for impact cards).
    side: "A"/"N" (aff/neg). event: pf | ld | cx | openev. Use plain keywords, e.g. "nuclear war escalation
    Taiwan" or "data center water". Run several phrasings; tags use debate shorthand ("econ", "heg", "prolif").
    """
    limit = max(1, min(limit, 30))
    if scope == "mine":
        return [dict(r) | {"id": f"c{r['id']}"} for r in store.search_cards(query, limit)]
    if not library.ready():
        raise ToolError("Card library not built yet. Call build_library (or run `pf-debate-mcp build-library`). "
                        "Meanwhile use web search + fetch_source + cut_card.")
    return library.search(query, limit, year_from, side, event, sort)


@mcp.tool()
def get_card(card_id: str, view: str = "read") -> str:
    """Card by id (lib:N or cN). view="read" (default, compact): tag, cite, and only the underlined/highlighted
    text (==highlighted== is read aloud, _underlined_ is context, ... marks skipped text). view="full": the whole
    body, needed to judge context, find indicts in unhighlighted text, or recut."""
    card = _card(card_id)
    if view != "full":
        read = f"\n(read by {card['times_read']} teams)" if card.get("times_read") else ""
        return render_read(card) + read
    extra = f"\n(read by {card['times_read']} teams; {card['origin']})" if card.get("times_read") else ""
    if not any(h for _, _, h in card["runs"]):
        extra += "\n(unmarked card: the team read it in full; recut it with cut_card to highlight)"
    return render(card) + extra


@mcp.tool()
def fetch_source(url_or_id: str, start_paragraph: int = 0) -> str:
    """Fetch an article/PDF (or re-open a source by id sN) as clean numbered paragraphs + citation metadata.
    Long sources are paged: call again with start_paragraph to continue. Copy quotes for cut_card exactly
    from this text."""
    if m := re.fullmatch(r"s(\d+)", url_or_id.strip()):
        row = store.get_source(int(m[1]))
        if not row:
            raise ToolError(f"Source {url_or_id} not found; call fetch_source with the URL.")
        sid, meta, text = row["id"], dict(row), row["text"]
    else:
        url = url_or_id.strip()
        row = store.find_source(url)
        if row:
            sid, meta, text = row["id"], dict(row), row["text"]
        else:
            try:
                meta, text = fetch(url)
            except FetchError as e:
                raise ToolError(str(e)) from None
            sid = store.add_source(url, meta, text)
    paras = paragraphs(text)
    out, size, i = [], 0, start_paragraph
    while i < len(paras) and size < 14000:
        out.append(f"[{i}] {paras[i]}")
        size += len(paras[i])
        i += 1
    more = f"\n... {len(paras) - i} more paragraphs: fetch_source('s{sid}', start_paragraph={i})" if i < len(paras) else ""
    head = (f"source_id: s{sid}\nurl: {meta.get('url')}\ntitle: {meta.get('title')}\nauthor: {meta.get('author')}\n"
            f"date: {meta.get('date')}\npublisher: {meta.get('publisher')}\n"
            "(metadata is auto-extracted: verify author and find their qualifications before citing)\n")
    return head + "\n".join(out) + more


@mcp.tool()
def cut_card(source_id: str, tag: str, author: str, date: str, title: str, publisher: str, url: str,
             quals: str, start_quote: str, end_quote: str, highlight: list[str],
             underline: list[str] | None = None, paragraph: int | None = None) -> str:
    """Cut an evidence card. The body is the exact source text from start_quote through end_quote
    (a few sentences to a few paragraphs; enough context that the author's meaning is clear).
    highlight = phrases read aloud; underline = wider phrases that give context (defaults to highlight).
    Every quote must be copied verbatim from the source (only whitespace, quote marks and dashes are
    normalized); anything else is rejected with a hint showing where the text stopped matching.
    source_id: sN from fetch_source, or a card id (cN, lib:N) to re-cut an existing card.
    paragraph: the [N] number from fetch_source where the card starts; required when start_quote appears
    more than once in the source."""
    sid = source_id.strip()
    if m := re.fullmatch(r"s(\d+)", sid):
        row = store.get_source(int(m[1]))
        if not row:
            raise ToolError(f"Source {sid} not found; call fetch_source first.")
        text = row["text"]
    else:
        text = ranges_from_runs(_card(sid)["runs"])[0]
    try:
        c = cut(text, start_quote, end_quote, underline or [], highlight, paragraph)
    except CutError as e:
        raise ToolError(f"REJECTED (card not saved): {e}") from None
    short, rest, cite_warn = format_cite({"author": author, "date": date, "title": title, "publisher": publisher,
                                          "url": url, "quals": quals, "accessed": None})
    cid = store.add_card(tag.strip(), short, rest, c["body"], c["underline"], c["highlight"], origin=sid)
    card = store.get_card(cid)
    warnings = c["warnings"] + cite_warn
    note = ("\nWARNINGS (fix with a re-cut if needed):\n- " + "\n- ".join(warnings)) if warnings else ""
    return f"Saved as c{cid}.\n{render(card)}{note}"


@mcp.tool()
def export_doc(title: str, items: list[dict], filename: str | None = None, format: str = "docx") -> str:
    """Write a speech doc / case / block file. items in order, each one of:
    {"pocket": "..."} {"hat": "..."} {"block": "..."} (Verbatim headings: Pocket > Hat > Block),
    {"tag": "..."} (analytic tag, no card), {"text": "..."} (speech prose), {"card": "c12" | "lib:345"}.
    format "docx": Verbatim-compatible Word file. format "gdocs": an .html file for Google Docs users (open it,
    select all, copy, paste into a Google Doc; or upload it to Google Drive and open with Google Docs).
    Returns the file path."""
    if format not in ("docx", "gdocs"):
        raise ToolError('format must be "docx" or "gdocs"')
    resolved = []
    for it in items:
        if "card" in it:
            resolved.append({"card": _card(it["card"])})
        elif len(it) == 1 and next(iter(it)) in ("pocket", "hat", "block", "tag", "text"):
            resolved.append(it)
        else:
            raise ToolError(f"Bad item {it}: use one key of pocket/hat/block/tag/text, or card.")
    name = filename or f"{title}-{date.today().isoformat()}"
    name = re.sub(r'[<>:"/\\|?*]', "", name).strip().removesuffix(".docx").removesuffix(".html") or "pf-doc"
    if format == "gdocs":
        path = export_html(title, resolved, store.EXPORT_DIR / f"{name}.html")
        return f"Saved {path} (open it, select all, copy, paste into Google Docs)"
    return f"Saved {export(title, resolved, store.EXPORT_DIR / f'{name}.docx')}"


@mcp.tool()
def caselist_search(query: str, caselist: str | None = None) -> list[dict]:
    """Search OpenCaselist (disclosed cases) for a team, debater last name, or argument text.
    Defaults to the current HS PF caselist; pass a slug like 'hspf25' for older ones. Limit: 4/min."""
    try:
        return cl.search(query, caselist)
    except cl.CaselistError as e:
        raise ToolError(str(e)) from None


@mcp.tool()
def caselist_team(school: str, team: str, caselist: str | None = None) -> dict:
    """A team's caselist page: rounds (tournament, side, opponent, round report, open-source file path)
    and cites (their disclosed cards). Use for scouting and building blocks against their case."""
    try:
        return cl.team(school, team, caselist)
    except cl.CaselistError as e:
        raise ToolError(str(e)) from None


@mcp.tool()
def caselist_download(path: str) -> str:
    """Download an open-source .docx from OpenCaselist (the 'opensource' path from caselist_team or a
    search 'download_path') and import its cards as cN ids you can read, analyze, re-cut or export."""
    try:
        data = cl.download(path)
    except cl.CaselistError as e:
        raise ToolError(str(e)) from None
    try:
        cards = parse(data)
    except Exception as e:  # corrupt or non-docx input: python-docx raises several unrelated types
        raise ToolError(f"Could not read {path} as a .docx ({type(e).__name__}).") from None
    lines = []
    for c in cards:
        body, ul, hl = ranges_from_runs(c["runs"])
        cid = store.add_card(c["tag"], c["cite_short"] or "", c["cite_rest"], body, ul, hl, origin=f"caselist:{path}")
        where = " > ".join(x for x in (c["pocket"], c["hat"], c["block"]) if x)
        lines.append(f"c{cid} [{where}] {c['tag']} -- {c['cite_short']}")
    return f"Imported {len(cards)} cards from {path}:\n" + "\n".join(lines) if cards else \
        f"No cards found in {path} (it may be analytics-only or a paraphrased case)."


@mcp.tool()
def library_status() -> dict:
    """Whether the local card library is built, how many cards per event, years covered, and build progress."""
    return library.status()


@mcp.tool()
def build_library(mode: str = "download") -> str:
    """Install the card library in the background (one time; resumable; progress via library_status).
    mode "download" (default): the prebuilt library (~170k cards incl. the most-read PF, LD, Policy and camp
    cards; a few minutes). "quick" / "full": build from the raw dataset instead (PF only in minutes, or
    everything in a few hours)."""
    if mode != "download" and mode not in library.PRESETS:
        raise ToolError(f"mode must be 'download' or one of {list(library.PRESETS)}")
    return library.start_background_build(mode)


@mcp.tool()
def pf_guide(name: str = "pf-debate") -> str:
    """PF debate knowledge. Read "pf-debate" first. Task guides: pf-case, pf-cut-card, pf-analyze,
    pf-blocks, pf-scout. References: glossary, format, tactics, impacts, evidence-ethics."""
    key = name.strip().lower().removesuffix(".md")
    for f in (SKILLS / key / "SKILL.md", SKILLS / "pf-debate" / "references" / f"{key}.md"):
        if f.exists():
            return f.read_text(encoding="utf-8")
    return "Unknown guide. Options: " + ", ".join(
        [d.name for d in SKILLS.iterdir() if d.is_dir()] +
        [f.stem for f in (SKILLS / "pf-debate" / "references").glob("*.md")])


def _const(text: str):
    return lambda: text


def _register_skills() -> None:
    from mcp.server.mcpserver.prompts import Prompt
    from mcp.server.mcpserver.resources import TextResource

    for f in sorted(SKILLS.rglob("*.md")):
        rel = f.relative_to(SKILLS).as_posix()
        text = f.read_text(encoding="utf-8")
        mcp.add_resource(TextResource(uri=f"skill://{rel}", name=rel, text=text, mime_type="text/markdown"))
        if f.name == "SKILL.md":
            desc = (re.search(r"^description:\s*(.+)$", text, re.M) or [None, ""])[1]
            mcp.add_prompt(Prompt.from_function(_const(text), name=f.parent.name, description=desc))


_register_skills()
