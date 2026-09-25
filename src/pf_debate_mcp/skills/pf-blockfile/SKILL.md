---
name: pf-blockfile
description: Use when a debater or team wants a block file, blockfile, master file, A2/AT file, frontline file, or "blocks for the whole topic" - a side-organized Word file of answers to every opposing argument, with numbered, labeled, carded responses.
---

# Building a PF block file

**REQUIRED BACKGROUND:** pf-debate (evidence rule), pf-cut-card (how cards are cut), pf-blocks (what makes a good response).

A block file is the team's shared answer bank for a topic. In round, the rebuttal speaker opens the argument the opponent just read, sees numbered responses with their cards, and reads 3–5 of them. So every choice below serves one thing: **find the block in seconds and read it cleanly**.

## What it looks like
Modeled on real PF team master files and published briefs. Verbatim heading levels, so Word's Navigation Pane (View > Navigation Pane) becomes a clickable table of contents:

```
LAKESIDE NOV/DEC 25 MASTER BLOCKFILE                      <- title (export_doc title)
Resolved: The USFG should require ... encrypted communications.
Label key: [NU] non-unique  [DL] delink  [T] turn ...      <- one line, for teammates

PRO / A2 CON                                               <- Pocket (H1): our side, answering theirs
  A2 Cyberattacks                                          <- Hat (H2): the opponent's argument, named as THEY say it
    1. [NU] Breaches tripled last year: cyber risk exists without the aff     <- Tag (H4) + card
       Chapple 25 [Mike Chapple; cybersecurity professor, Notre Dame; ...; URL]
       ...card text, read portion bold + underlined + highlighted...
       - Their risk is the status quo baseline; the question is who manages it   <- warrant bullet
    2. [DL] Lawful access isn't a universal backdoor: warrant-gated, per-case keys   <- analytic response
       - Court order first; companies keep keys; access is per case
    3. [T] Lawful access lets police stop cyber gangs before they strike   <- turn, with its card
  A2 Economy                                               <- Hat
    Overview                                               <- Block (H3): optional sub-grouping
    A2 Investor Confidence                                 <- Block (H3): a sub-argument of the hat
      1. [NI] ...
  Weighing                                                 <- Hat: pre-written weighing for summary/FF
CON / A2 PRO                                               <- Pocket: the other side (PF debaters flip)
  A2 Child Exploitation
  ...
PRO FRONTLINES                                             <- Pocket (optional): defending our own case
  FL C1: Grid costs                                        <- Hat: our contention
    A2 "Utilities absorb the costs"                        <- Block: the response we expect
      1. ...
```

## The rules that make it usable
- **Pockets by side.** `PRO / A2 CON` holds the Pro side's answers to Con arguments; `CON / A2 PRO` the reverse. Frontlines for the team's own cases get their own pocket (`PRO FRONTLINES`, `CON FRONTLINES`). Use the team's own naming if they have one (some teams write `2AC / A2 NEG`).
- **One hat per opposing argument**, titled `A2 <their argument>` in the words the opponent would use ("A2 Cyberattacks", "A2 Econ DA", "A2 Nuke Terror"). A teammate must recognize it from the opponent's tag. Use `AT:` or `A/2` instead only if the team already does.
- **Blocks (H3) only when they help:** an `Overview` (1–3 lines of framing to read first), or sub-arguments inside a big hat (`A2 Investor Confidence` under `A2 Economy`). Don't create a block per response.
- **Every response is a numbered, labeled tag**: `1. [NU] <claim>`. Number across the hat (1, 2, 3...). The claim is one sentence that makes sense read alone and says what it does to THEIR argument ("Breaches tripled last year: cyber risk exists without the aff"), and it never claims more than the card's highlighting proves.
- **Labels** (use the team's set if they have one; default):

  | Label | Means | Response must show |
  |---|---|---|
  | [NU] | Non-unique | Their harm/benefit already happens (or won't) without the resolution |
  | [DL] | Delink / no link | The resolution doesn't cause their link |
  | [T] | Turn (write [LT]/[IT] if the team distinguishes) | The resolution causes the OPPOSITE: offense for us. Give it an impact line |
  | [NI] | No impact / impact defense | Even if the link holds, the impact is small, slow, or improbable |
  | [AC] | Alt cause | Something else causes their impact; the resolution isn't the key factor |
  | [M] | Mitigation | Their impact is real but smaller than they say |
  | [X] | Cross-apply | Reuse an answer already in the file: "[X] Cross-apply 1 from A2 Backdoors" |
  | [W] | Weighing | Why our impact outweighs even if theirs holds |
- **Order:** defense that sets up the turn first, turns last with their impact (the file's usual flow is NU, DL, NI/AC, then T). Strongest first within each type. **Never put a link turn and an impact turn on the same argument** (double turn), and don't run [NU] against an argument you also [T] on uniqueness grounds without checking they're consistent.
- **3–6 responses per hat**, at least half carded. Analytics are welcome if they are labeled "(analytic)" in the tag or obvious, and backed by warrant bullets.
- **Warrant bullets** (`{"text": "- ..."}`) under a response: the 1–3 reasons the rebuttal speaker explains in their own words. Put them right after the card (or right after an analytic tag).
- **Cards** follow pf-cut-card: bold `Author YY` short cite plus a full cite with **quals**, date, title, publication, URL, access date; read text highlighted; highlight so the read text is grammatical. Never insert bracketed words or change text: `cut_card` only accepts exact source text (some team guides allow [brackets]; this tool doesn't).
- **Short reads.** A rebuttal answers a whole case in 4:00, so each response should read in about 10–20 s and a whole hat in 30–60 s. Check a hat with `read_speech(items_for_that_hat, "rebuttal", wpm)`; trim long highlighting.

## Workflow
1. **Scope.** Get: the resolution (confirm the current topic by web search), the team name for the title, the team's cases if they share them, their label/naming conventions (or use the defaults), and the debater's pace.
2. **List the arguments to block, per side.** Sources, best first:
   - what the user has seen at tournaments or knows teams run;
   - pf-scout topic analysis (the standard contentions each side will read);
   - on local installs, `caselist_search` / `caselist_team` + `caselist_download` for what teams actually disclosed;
   - for frontlines, the responses the team's own contentions will face.
   Show the list as a plan (pocket > hats > 2–3 planned response labels each) and **confirm before cutting**. It sets how much work follows.
3. **Build in batches of 3–5 hats.** For each hat:
   - Map their argument (UQ, link, internal link, impact) so every response hits a specific step.
   - Evidence: `search_cards` first (past topics on the same issue often have strong defense and impact cards; check dates), then `auto_cut("<response claim>")` for current evidence, or `find_sources` → `fetch_source` → `suggest_cut` → `cut_card` for a specific source.
   - Write the tags to match exactly what each card's highlighting proves (retag with `{"card": id, "tag": "..."}`).
4. **Export after every batch** (cards on the free server expire; exported files don't): `export_doc(title="<TEAM> <TOPIC> MASTER BLOCKFILE", items, version="full")`. When all batches are done, export the whole file in one call, and offer `version="read"` (each hat marked with its read time).
5. **Report:** the hats built, which responses are still analytics-only (the team's cutting to-do list), and any hat that reads over 60 s.

## Item mapping for export_doc
```
{"text": "Resolved: ..."}
{"text": "Label key: [NU] non-unique, [DL] delink, [T] turn, [NI] no impact, [AC] alt cause, [W] weighing"}
{"pocket": "PRO / A2 CON"}
{"hat": "A2 Cyberattacks"}
{"block": "Overview"}, {"text": "Their cyber story assumes..."}                    (optional)
{"card": "c_91ab", "tag": "1. [NU] Breaches tripled last year: cyber risk exists without the aff"}
{"text": "- Their risk is the baseline; the aff only adds oversight"}
{"tag": "2. [DL] Lawful access isn't a universal backdoor (analytic)"}
{"text": "- Court order first"}, {"text": "- Keys stay with the company, per case"}
{"card": "lib:48213", "tag": "3. [T] Lawful access lets police stop ransomware gangs before they strike"}
{"hat": "Weighing"}, {"tag": "Probability: their cyber harm is already happening..."}
{"pocket": "CON / A2 PRO"} ...
```

## Common mistakes
- Hats named after our response ("Encryption is safe") instead of their argument ("A2 Backdoor Security"): nobody finds it mid-round.
- Unnumbered or unlabeled responses: the speaker can't say "1, non-unique..." and the judge can't flow it.
- A tag that says more than the highlighted text (powertag), or one that only makes sense with the heading ("Also true").
- Only defense and no turns: a block file should give the speaker offense on the arguments they'll collapse against.
- Long cards: a 90-word highlight in a rebuttal block costs 30 s. Trim it.
- Building the whole topic in one pass on the free server and losing cards: export every batch.
