---
name: pf-scout
description: Use when a debater starts prep on a new PF topic, asks for a topic analysis or prep plan, wants to know common arguments on a resolution, or wants to scout an opponent, look up a team's caselist or disclosed case, or prepare for a specific round.
---

# Topic prep and scouting

**REQUIRED BACKGROUND:** pf-debate.

## Topic dashboard (new resolution)
1. Confirm the exact resolution and its dates (web search).
2. **Definitions:** For each key term (e.g. "moratorium", "hyperscale"), give 1–2 carded definitions and note ambiguities to exploit.
3. **Burdens:** What must each side prove? Is it plan-like ("should enact") or comparative?
4. **Argument map:** The top 4–5 arguments per side, each as UQ → link → impact with its likely terminal impact, the best weighing, and the main answers. Check `search_cards` for existing cards on each (older topics often overlap: energy, AI, China, econ).
5. **Prep plan:** Which cases to write first, which blocks are needed, and the evidence gaps to research.
6. Offer to export as a doc: pocket per side, block per argument.

## Scouting an opponent
1. `caselist_search("<team or last name>")`, then `caselist_team(school, team)`. The default is the current HS PF caselist. Login problems get the user pointed to `uvx pf-debate-mcp login`.
2. Read the round reports: which contentions they run on each side, and what they collapse to.
3. `caselist_download(path)` their most recent open source for the side you'll face. Then use pf-analyze on each contention.
4. Deliver a one-page scout: their case per side, the key cards, the weak links, CX questions, and the blocks to pull or write (pf-blocks).

## Prep out a tournament ("prep out everyone at <tournament>")
1. **Get the field.** Tabroom entry pages usually need a login, so ask the user to export it: on the tournament's Tabroom page, open Entries (Fields), pick the PF event, and download the CSV (or paste the list). Pass the file's text to `caselist_entries(entries)`. It needs the user's own caselist login (see "Login" below).
2. **Triage** the result into: disclosed with open source, disclosed cites only, not disclosed. Tell the user the counts.
3. **Pull cases, grouped by argument, not by team.** `caselist_download` the latest open source per side for disclosed teams (10 downloads/min: pace it, newest first). Read each contention and cluster: most fields run a handful of arguments. Name each cluster the way teams tag it ("Cyberattacks", "Child exploitation").
4. **Blocks.** One `A2 <argument>` hat per cluster via pf-blockfile, strongest/most-run first, using the actual cards teams read (their tags and authors) so the responses hit them. Non-disclosing teams: cover the standard topic arguments (topic dashboard above).
5. **Team sheets.** One short entry per team: side-by-side case summary, who they are (record from rounds if disclosed), cards to indict, 3 CX questions, which A2 hats to pull. Export as a doc: `{"pocket": "Team sheets"}`, `{"hat": "<School> <Last & Last>"}` per team, then the block file pockets.
6. Big fields cost a lot of usage: offer to do the most-likely opponents (same bracket, strong records) first.

## Login (caselist tools)
The caselist tools run only in the local plugin (Claude Code, CLI or desktop app). The user logs in once in their own terminal window (PowerShell/Terminal, not the chat) with `uvx pf-debate-mcp login`; it asks for their Tabroom email and password there, saves only the session token on their computer, and never stores the password. **Never ask the user to type their password into the chat.** If a caselist tool says "Not logged in" or "session expired", tell them to run that command, then retry.

Rate limits: 4 searches and 10 downloads per minute. Batch your thinking and don't spam calls.
