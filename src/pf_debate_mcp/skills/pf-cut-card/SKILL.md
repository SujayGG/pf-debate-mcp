---
name: pf-cut-card
description: Use when a debater asks to cut a card, find evidence or a source for a claim, recut or retag a card, or get cards for an argument (PF, LD, or policy debate).
---

# Cutting cards

**REQUIRED BACKGROUND:** pf-debate (evidence rule) and its references/evidence-ethics.md.

## Workflow
1. **Library first.** Use `search_cards(query)` with 2–4 phrasings (debate shorthand helps: "econ decline war", "heg", "prolif"). For impacts, add `sort="popular"`. `get_card` the promising ones. A strong existing card beats a new cut. For new facts about the current topic, the library (2013–2024) will often have nothing: go to the web.
2. **Web.** Use your own web search for recent, qualified sources: think tanks, academic papers, government reports, and major outlets. Prefer sources that contain the warrant, not just the claim.
3. **`fetch_source(url)`** returns numbered paragraphs plus metadata. If it errors (paywall or JS page), pick another source. Never cut from a search snippet or from memory.
4. **Find the author's quals** (their bio on the page, or search "<author> <outlet>").
5. **`cut_card`:**
   - `start_quote` / `end_quote`: the first and last few words of the card body, copied exactly. Take enough context (usually 1–3 paragraphs).
   - `highlight`: the phrases read aloud, in order, copied exactly. Together they should read as grammatical sentences that prove the tag.
   - `underline`: wider phrases for context (optional; defaults to the highlight).
   - `tag`: one sentence the highlighted text actually proves. It should be arguable and specific ("Moratorium cedes the compute race to China"), not a restatement.
6. On **REJECTED**, re-read the source text and copy it exactly (the hint shows where it diverged). On **WARNINGS**, fix and re-cut if it matters (missing quals, a thin body).
7. Show the user the card (the `get_card` format). Offer `export_doc`.

## Recut / retag
`cut_card(source_id="lib:123" or "c5", ...)` re-marks an existing card's text for a new tag. The same verbatim rules apply.

## Common mistakes
- Tagging beyond the highlight (powertag). If the card says "could", the tag says "risks", not "causes".
- Highlighting that skips a "not" or "unlikely" and flips the meaning.
- Cutting from a press release that summarizes a study when the study itself is fetchable. Cut the study.
- Using a 2016 card for a fast-moving fact (AI compute, energy prices).
