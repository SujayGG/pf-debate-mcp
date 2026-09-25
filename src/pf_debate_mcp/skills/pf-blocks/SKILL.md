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

## Team block file
A block file is the team's shared prep for the whole topic: every argument the opponents may run, answered in advance, plus frontlines for the team's own case. It is organized so the rebuttal speaker finds a block in seconds from Word's Navigation Pane (View > Navigation Pane), which lists the headings.

1. **Scope it.** Get the resolution and the team's cases (both sides: PF debaters flip). List the arguments to block:
   - The opponents' likely contentions on each side: topic analysis (pf-scout), what the user has seen at tournaments, and on local installs `caselist_search`/`caselist_team` for what teams actually run.
   - The responses the team's own contentions will face (for frontlines).
   Confirm the list with the user before cutting. It sets how much work follows; build in batches of 3–5 blocks if the list is long.
2. **Structure** (Verbatim levels, so it opens cleanly in Verbatim and plain Word):
   - Pocket = side: `{"pocket": "Pro"}`, `{"pocket": "Con"}`.
   - Hat = one argument: `{"hat": "AT: Data centers create jobs"}` (answers to their argument), or `{"hat": "Frontlines: C1 Grid costs"}` (defending our contention).
   - Block = a group of responses inside it: `{"block": "Turns"}`, `{"block": "Defense"}`, `{"block": "Weighing"}`. For a frontline, one block per response it answers: `{"block": "A2: Grid upgrades pay for themselves"}`.
   - Each response: a numbered tag, then its card. `{"tag": "1. TURN: ..."}` plus `{"card": id, "tag": "..."}` if the card's tag should carry the claim, or `{"text": "1. DEFENSE (analytic): ..."}` for an analytic. Number responses across the whole hat (1, 2, 3...), strongest first.
   - Optional: an `{"hat": "Overviews/Weighing"}` at the top of each pocket with pre-written weighing the summary speaker can read.
3. **Cards.** Every response with a card follows pf-cut-card (`auto_cut` or `search_cards` first). Labeled analytics are fine for logic responses; never write a fake card. Aim for a short read on each: rebuttal blocks should run 20–45 s each, so check with `read_speech(items_for_that_hat, "rebuttal", wpm)`.
4. **Deliver.** `export_doc(title="<Topic> Block File", items, version="full")` for the team file. Offer `version="read"` too (every block carries its read time, so the rebuttal speaker can budget 4:00). Tell the user which arguments still have only analytics, so the team knows what to cut next. On the free server, cut cards expire after a while: export at the end of each batch so nothing is lost.

## Writing a speech
Check the word budget in format.md. Use signposting and an off-time roadmap.
- **Rebuttal:** Turns first. Number the responses. In 2nd rebuttal, frontline the arguments you will collapse to, and every turn.
- **Summary:** Collapse to 1–2 arguments. Extend each with warrants and card names. Frontline. Extend the needed defense/turns on their case. Weigh comparatively.
- **Final focus:** The same collapse and weighing as summary, as voting issues. No new arguments.
- **Dropped argument:** Extend it with its full warrant, say "this was conceded in <speech>", then weigh it. A dropped turn with no impact extension does nothing.
- **Kicking:** To escape a turn, concede their defense on that argument so the turn has no link.
