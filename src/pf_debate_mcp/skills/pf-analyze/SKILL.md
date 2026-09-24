---
name: pf-analyze
description: Use when a debater asks to analyze, rate, check, or indict a card, a case, or an opponent's evidence, or wants crossfire questions or answers against specific evidence.
---

# Analyzing cards and cases

Get the text first: `get_card(id, view="full")` for cN or lib:N ids (the full view shows the unhighlighted text, where indicts live), `caselist_download` for opponent open-source docs, or the text the user pasted.

## Card checklist
| Check | Ask |
|---|---|
| Tag vs highlight | Does the highlighted text alone prove the tag? If not, it's a powertag. Quote the gap. |
| Unhighlighted text | What does the skipped text concede ("unlikely", "some argue", "in the short term")? That's an indict. |
| Warrant | Is there a reason, or only an assertion? |
| Quals | Is the author an expert in *this* claim? Blog, advocacy group, or funded source? |
| Date | Recent enough for the claim? Has something changed since? |
| Context | Does the card cut out the author's own rebuttal? |
| Fit | Does the card's scenario match the resolution's action (scope, actor, timeframe)? |

Rate each card: **strong / usable / weak / indictable**, with one line of why.

## Case checklist
For each contention, map UQ, link, IL and impact, and name the card on each step. Flag steps with no card, or with an analytic doing card work. Find the weakest link. Check its weighing (is it comparative?). Note the turns-case or link-in opportunities for the *other* side.

## Output
1. The verdict per card or contention.
2. **Responses** in rebuttal-ready form, numbered, with turn vs defense labeled (use pf-blocks to write them out with cards).
3. **Crossfire questions**: 3–5 short, closed questions that expose the gaps.
4. If it's the user's own evidence: concrete fixes (a recut via `cut_card`, or a better source to find).
