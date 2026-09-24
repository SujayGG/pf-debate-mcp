---
name: pf-case
description: Use when a debater asks to build, write, or improve a PF case, contention, constructive, advantage, or disadvantage, including cases centered on a specific impact (nuclear war, extinction, econ, climate, structural violence) or for a given side of a resolution.
---

# Building a case

**REQUIRED BACKGROUND:** pf-debate. Read references/impacts.md and references/tactics.md (case construction).

## 1. Pin down the ask
Get the resolution (confirm the current topic by web search if it's not given), the side, and the judge type. Take the user's framing literally: "centered around a nuclear impact" means every contention's terminal impact is nuclear war, or funnels into it.

## 2. Plan (confirm before cutting)
- **Standard mode:** Brainstorm 3–5 arguments for the side, then pick the 2 with the best link evidence and weighing.
- **Impact-first mode** (the user named an impact): Start from impacts.md's chains for that impact, then work backward. What does the resolution change that starts the chain? Pick the shortest plausible chain.
- Present the plan as a flow: `C1: <tag> — UQ: … → Link: … → IL: … → Impact: …` plus a weighing line. Ask the user to confirm or adjust. This checkpoint matters; skip it only if they said "just do it" or "auto".

## 3. Evidence for every step
For each step, first `search_cards` (impact cards: `sort="popular"`), then web search → `fetch_source` → `cut_card` for topic-specific links and uniqueness. Follow pf-cut-card. One card per step minimum. Stack two on the step the opponent will attack (usually the internal link). Missing evidence means a labeled analytic plus a note to the user. Never write a fake card.

## 4. Write it
- A short intro and a resolution/definitions line if useful.
- Each contention: a tag-line claim, then cards in chain order, with 1–2 sentences of analysis between cards that make the link explicit ("This matters because...").
- Framing/weighing: why this impact outweighs the likely opposing impacts (magnitude/probability/timeframe; turns case).
- Fit the length: 4:00 means about 650–750 spoken words for lay, 850–1000 for circuit. Count only highlighted card words, tags, and prose.

## 5. Deliver
`export_doc` with items in order: `{"pocket": "<Side> Case"}`, then per contention `{"block": "C1: ..."}`, `{"text": analysis}` and `{"card": id}`, and finally the framing block. Give the user the path, a word-count and time estimate, and the 2–3 most likely responses (hand off to pf-blocks).
