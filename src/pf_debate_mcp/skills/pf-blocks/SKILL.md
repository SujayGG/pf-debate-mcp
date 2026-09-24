---
name: pf-blocks
description: Use when a debater needs blocks, frontlines, "AT"/answers-to responses, turns, or a written rebuttal, summary, or final focus, or asks what to do after an argument was dropped or turned.
---

# Blocks, frontlines, and later speeches

**REQUIRED BACKGROUND:** pf-debate. Read references/format.md (what each speech must do) and references/tactics.md.

## Blocks (AT: <argument>)
1. Get the argument precisely: the user's description, `get_card`, or the opponent's doc via `caselist_download`. Map its UQ/link/IL/impact (pf-analyze).
2. Write 4–6 numbered responses, strongest first, each labeled **TURN** / **DEFENSE** / **WEIGHING**:
   - Turns: a link turn OR an impact turn, never both on the same argument (a double turn).
   - Defense: NUQ, delink, mitigation, alt causes, evidence indicts.
   - Weighing: why your impact matters more even if they win theirs.
3. Back each response with a card (pf-cut-card; library first) or mark it "analytic".
4. Export: `{"pocket": "Neg Blocks"}` / `{"block": "AT: Econ"}` then `{"tag": response claim}` or `{"card": id}` for each response.

## Frontlines (answers to responses against YOUR case)
For each likely response: explain why it's wrong or doesn't apply, with a card where possible, then re-establish your link. Prioritize answering turns. They are offense for the other side.

## Writing a speech
Check the word budget in format.md. Use signposting and an off-time roadmap.
- **Rebuttal:** Turns first. Number the responses. In 2nd rebuttal, frontline the arguments you will collapse to, and every turn.
- **Summary:** Collapse to 1–2 arguments. Extend each with warrants and card names. Frontline. Extend the needed defense/turns on their case. Weigh comparatively.
- **Final focus:** The same collapse and weighing as summary, as voting issues. No new arguments.
- **Dropped argument:** Extend it with its full warrant, say "this was conceded in <speech>", then weigh it. A dropped turn with no impact extension does nothing.
- **Kicking:** To escape a turn, concede their defense on that argument so the turn has no link.
