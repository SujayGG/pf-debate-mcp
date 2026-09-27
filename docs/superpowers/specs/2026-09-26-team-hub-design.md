# Team hub (phase 1: tournament day): design

Date: 2026-09-26. Status: approved design, pending spec review.

## Goal
Repurpose debate.peshcompsci.org from a card-finder web app into a free, public, phone-first "better Tabroom" hub. Phase 1 nails **tournament day**: one screen per followed entry showing the current round, opponent, judge, record, and live "will I break" odds. The MCP connector and the Claude Code plugin keep their purpose (evidence, cases, blocks); the current card finder moves to `/cards`.

Audience: any debater or team, no accounts. Later phases: scouting (phase 2), season tracking (phase 3). Out of scope here: team spaces, notifications, rankings/bids, evidence-source upgrades (separate spec).

## Research facts this relies on (verified 2026-09-26)
- Tabroom's official API, **IndexCards v1.2.0**, at `https://api.tabroom.com/v1` (OpenAPI 3.1 served at that URL; Scalar reference at `/v1/reference`). Terms: https://www.speechanddebate.org/terms-conditions/.
- Public (no auth), verified live: `GET /rest/tourns/{tournId}`, `/rest/tourns/{tournId}/rounds`, `/rest/tourns/{tournId}/schedule`, `/rest/tourns/{tournId}/invite`, `/rest/tourns/{tournId}/results`, `/rest/tourns/{tournId}/events/{eventAbbr}/field` (eventAbbr as on Tabroom, e.g. `VPF`; returns Entries with School and Students), `/pages/invite/upcoming`.
- Public per the spec, not yet verified live (Tabroom went down mid-test): `/rest/tourns/{tournId}/entries/{entryId}/records` ("published pairings and results data for a given entry"), `/pages/invite/{tournId}/{eventAbbr}/{roundName}` (round sections with results if public), `/rest/tourns/{tournId}/results/{resultSetId}`, `/rest/tourns/{tournId}/events/{eventId}/results`.
- Auth required (401 without): `/rest/paradigms`, `/rest/paradigms/{personId}`, `/rest/paradigms/{personId}/record` (JudgeRecord: Tourn, roundDate, roundLabel, eventAbbr, affTeam/affLabel, negTeam/negLabel, ...). Auth = bearer token from `POST /auth/login` or the `TabroomToken` cookie.
- Tabroom HTML pages: pairings postings are public; fields, results and paradigm pages need login.
- Tabroom can be down or overloaded (returned its "Site Maintenance" HTML with 503 during the Prosper Eagles tournament on 2026-09-26). No rate-limit headers; no CORS headers observed.
- OpenCaselist API (`https://api.opencaselist.com/v1`) needs a Tabroom-derived login token (cookie `caselist_token`).
- debate.land / tournaments.tech: unofficial, data only 2020–22, site unreachable. Not used.

## Architecture
```
phone ──▶ debate.peshcompsci.org (Cloudflare Worker, free plan)
            ├─ /             hub (new)
            ├─ /cards        current card finder (moved from /app, unchanged; /app redirects here)
            ├─ /mcp, /api/*  connector + card API (unchanged; Workers VPC → backend)
            └─ /t/api/*      hub API: Worker ─▶ api.tabroom.com/v1 public endpoints
                               └─ Cloudflare Cache API (short TTL) + KV (last good copy)
Chrome extension ─▶ api.tabroom.com (user's own Tabroom session) and api.opencaselist.com (user's own caselist session)
                 ─▶ passes results to the hub page in the same browser only
```
- The hub never depends on the backend PC/Oracle VM.
- The Worker calls only public Tabroom endpoints and never receives credentials or tokens.

## Units
1. **`deploy/worker/hub/tabroom.js`**: a thin client for the public endpoints. Each function returns plain mapped objects (`tourn`, `events`, `schedule`, `field`, `entryRecord`, `upcoming`). Mapping is isolated so schema drift breaks one place.
2. **`deploy/worker/hub/cache.js`**: `cached(key, ttl, fetcher)`.
   - Order: Cache API hit → fetch Tabroom → on success, write the Cache API (ttl) and, for followed-entry keys, KV (last good copy).
   - On failure (non-2xx, HTML body, or timeout after 8 s), serve the KV copy with `stale: true, asOf`.
   - Tabroom's maintenance HTML counts as a failure.
3. **Hub routes in `worker.js`**: `/t/api/upcoming`, `/t/api/tourn/:id`, `/t/api/tourn/:id/field/:event`, `/t/api/tourn/:id/entry/:entryId`. Plus page routes `/`, `/t/:id`, `/t/:id/entry/:entryId`, `/break`, all serving one hub HTML app.
4. **`deploy/worker/hub.html`**: a single-file phone-first app (no framework, same approach as the current app.html). It holds followed tournaments and entries in localStorage (wrapped in try/catch), auto-refreshes the entry screen every 60 s while visible, and always shows the "last updated" stamp and the stale banner.
5. **`deploy/worker/hub/breakmath.js`**: a pure module shared by the page and the tests.
6. **`extension/`**: Chrome MV3.
   - `host_permissions`: `https://api.tabroom.com/*`, `https://api.opencaselist.com/*`, `https://debate.peshcompsci.org/*`.
   - A content script on hub pages answers the page's requests (`postMessage`, with origin checked) by calling the two APIs with `credentials: "include"` from the extension's background worker.
   - Nothing is sent to our server.

## Pages
1. **Home:** search box (tournament name or Tabroom URL/ID), a "This weekend" list from `/pages/invite/upcoming` (filter by state/circuit), and followed tournaments.
2. **Tournament `/t/:id`:** name, dates, city; events with entry counts; the schedule by timeslot; a field per event (entry name, school, students). Each entry has "Follow" and a caselist link (a deep link to the school/team page when the name matches, otherwise caselist search).
3. **Entry `/t/:id/entry/:entryId`** (the core screen):
   - the current/next round: label, side, room, opponent, judges, start time;
   - the record so far, per round (W/L, side, opponent);
   - a break-odds meter;
   - an opponent card and judge cards;
   - an always-visible "Updated 2:41 PM" stamp.
   The URL is shareable.
4. **Break calculator `/break`:** standalone; prefilled when opened from an entry.

## Break math
- Monte Carlo, 10,000 simulations, in the browser.
- Unplayed prelims are paired by the rules:
  - rounds 1–2 random;
  - from round 3, power-matched within win brackets, high-low by current wins (ties by a random seed);
  - an odd bracket pulls up the top team of the next bracket.
- Unplayed rounds are 50/50.
- The break: top N by wins, with ties split by random order, standing in for tiebreaks we can't see.
- Output:
  - the probability of clearing at each final record;
  - the "safe" record (≥ 95% clear) and the "bubble" record (5–95%);
  - the entry's current probability of clearing given its record so far.
- Inputs:
  - field size and prelim count come from Tabroom (field and rounds);
  - the break size is user input, defaulting to the largest power of two ≤ field/4, minimum 2;
  - rounds already played use the entry's real record, and other teams get a record distribution consistent with the round.
- Accepted approximation, stated on screen: unknown tiebreaks (speaks, opp wins).

## Chrome extension
- **Judge card:** paradigm text via `/rest/paradigms/{personId}`, plus a local summary by keyword rules (speed, theory, kritiks, "lay", evidence preferences). The summary is heuristic and says so. The record via `/rest/paradigms/{personId}/record`: rounds this season, Pro/Con split, and dissent rate on panels where decisions are visible. A link opens the full paradigm.
- **Opponent card:** caselist disclosure (the team found / rounds disclosed / cite titles per side) and a link to the latest open-source doc.
- **Without the extension, or when logged out:** the card shows an install or log-in prompt plus a link to Tabroom.
- **Web Store:** publishing is a one-time $5 fee, which needs the owner's OK. Until then it's distributed as an unpacked zip with install steps.

## Error handling
| Situation | Behavior |
|---|---|
| Tabroom down, cached copy exists | Show the copy, banner "Tabroom is down; showing data from <time>" |
| Tabroom down, no copy | "Tabroom is down; retrying" and retry every 60 s |
| Round not paired | "Round 3 not paired yet (scheduled 1:30 PM)" from the schedule |
| Bye / dropped entry / hidden tournament | A specific plain-language message |
| Extension session missing/expired | "Log in to Tabroom in this browser, then refresh" |
| Schema drift (mapper throws) | Log the counter, show "Tabroom changed something; showing what we can" plus a raw link to the Tabroom page |

## Limits and politeness
- TTLs:
  - entry records and round sections: 60 s;
  - field, schedule, invite, rounds: 10 min;
  - upcoming: 1 h;
  - tournament: 1 h.
- Every Tabroom request carries a User-Agent naming pf-debate hub with a contact email.
- There's a per-IP rate limit on `/t/api/*` using the Worker's existing limiter pattern.
- KV writes happen only for followed-entry keys, and a daily write budget (≤ 900 of the free 1,000) skips KV writes past the cap.
- Before launch, email help@tabroom.com describing the hub and its caching.

## Testing
- `breakmath` unit tests:
  - deterministic with a seed;
  - with 64 teams, 6 prelims and a break of 16, 4–2 is the bubble and 5–1 is safe;
  - with 24 teams, 4 prelims and a break of 4, the probabilities are monotonic in wins.
- Mapper tests on saved real Tabroom responses (field already captured; records and rounds captured once Tabroom is back).
- A cache test with Tabroom mocked as down (HTML 503) serving the KV copy with `stale`.
- A live check on the next tournament weekend, plus the nightly smoke test extended with `/t/api/upcoming`.

## Non-goals (phase 1)
Accounts or team spaces, push notifications, rankings and bids, whole-field scouting, judge analytics across seasons, the evidence-source upgrades (separate spec), and moving the connector off the PC (the Oracle work continues separately).
