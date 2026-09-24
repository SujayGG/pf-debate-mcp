---
name: pf-cut-card
description: Use when a debater asks to cut a card, find evidence or a source for a claim, recut or retag a card, or get cards for an argument (PF, LD, or policy debate).
---

# Cutting cards

**REQUIRED BACKGROUND:** pf-debate (evidence rule) and its references/evidence-ethics.md.

## Workflow
0. **Fast path:** `auto_cut(claim)` returns the best library cards plus new verified cuts from fresh papers and news in one call. Rewrite each tag to what its highlight actually proves, and add missing quals. Use the steps below when you need more control or auto_cut found nothing.
1. **Library first.** Use `search_cards(query)` with 2–4 phrasings (debate shorthand helps: "econ decline war", "heg", "prolif"). For impacts, add `sort="popular"`. `get_card` the promising ones (the default compact view shows only the read text; use `view="full"` to check context before relying on a card). A strong existing card beats a new cut. For new facts about the current topic, the library (2014–2022) will often have nothing: go to the web.
2. **New sources.** `find_sources(query)` returns recent papers (with author affiliations for quals, plus free PDFs) and current news. Your own web search works too. Prefer qualified sources (think tanks, academic papers, government reports, major outlets) that contain the warrant, not just the claim.
3. **`fetch_source(url)`** returns numbered paragraphs plus metadata. If it errors (paywall or JS page), pick another source. Never cut from a search snippet or from memory.
4. **Find the author's quals** (their bio on the page, or search "<author> <outlet>").
5. **`suggest_cut(source_id, claim)`** proposes the best passage and highlights, all exact source text. Check them against the claim, then adjust and pass them to cut_card.
6. **`cut_card`:**
   - `start_quote` / `end_quote`: the first and last few words of the card body, copied exactly. Take enough context (usually 1–3 paragraphs).
   - `highlight`: the phrases read aloud, in order, copied exactly. Together they should read as grammatical sentences that prove the tag.
   - `underline`: wider phrases for context (optional; defaults to the highlight).
   - `tag`: one sentence the highlighted text actually proves. It should be arguable and specific ("Moratorium cedes the compute race to China"), not a restatement.
7. On **REJECTED** (returned as an error; the card is not saved), re-read the source text and copy it exactly (the hint shows where it diverged). If the start_quote appears more than once, pass `paragraph=<N>` from the [N] numbers in `fetch_source`. On **WARNINGS**, fix and re-cut if it matters (missing quals, a thin body).
8. Show the user the card (the `get_card` format). Offer `export_doc`.

## Recut / retag
`cut_card(source_id="lib:123" or "c5", ...)` re-marks an existing card's text for a new tag. The same verbatim rules apply.

## Common mistakes
- Tagging beyond the highlight (powertag). If the card says "could", the tag says "risks", not "causes".
- Highlighting that skips a "not" or "unlikely" and flips the meaning.
- Cutting from a press release that summarizes a study when the study itself is fetchable. Cut the study.
- Using a 2016 card for a fast-moving fact (AI compute, energy prices).
