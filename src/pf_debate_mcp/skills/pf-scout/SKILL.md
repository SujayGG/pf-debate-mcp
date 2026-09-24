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

Rate limits: 4 searches and 10 downloads per minute. Batch your thinking and don't spam calls.
