# Team hub phase 1 (tournament day): implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, phone-first tournament-day hub at debate.peshcompsci.org, built on Tabroom's official public API, with break math and a Chrome extension for login-only data.

**Architecture:** The Cloudflare Worker gains `/t/api/*` routes that call `api.tabroom.com/v1` public endpoints. Responses go through a cache layer (Cache API with a short TTL, plus a KV last-good copy), so pages keep working when Tabroom is down. A single-file hub page renders it, and break math runs client-side from a pure ES module the Worker also serves. The card finder moves to `/cards`.

**Tech Stack:** Cloudflare Workers (ES modules, Cache API, KV), vanilla HTML/JS, `node --test` (Node 24, no new deps), Chrome MV3.

**Spec:** `docs/superpowers/specs/2026-09-26-team-hub-design.md`

## Global Constraints
- $0: Workers free plan, KV free tier (1,000 writes/day). No new npm dependencies.
- The Worker calls only public Tabroom endpoints and never handles credentials.
- Every Tabroom call carries a User-Agent naming "pf-debate hub" and https://debate.peshcompsci.org/about.
- TTLs: entry records and round schematics 60 s; schedule, field and tournament 10 min; upcoming 1 h.
- Tabroom's maintenance page (HTML, 503) is a failure, never data.

## Tabroom API facts (from indexcards source, `api/services/results/entryRecords.js`, `api/controllers/pages/invite/schematController.js`)
- `GET /pages/invite/{tournId}/{eventAbbr}/{roundName}` → round `{id,name,label,type,startTime,published,postPrimary,Event,Sections:{sectionId:{Room:{name,url},bye,flight,bracket,Entries:{"1"|"2":{id,code,record,wins,pullup}},Judges:{id:{first,last,paradigm(personId),chair}}}}}`. Keys "1" and "2" are sides (1 = aff/Pro).
- `GET /rest/tourns/{tournId}/entries/{entryId}/records` → `{id,code,name,Event,Rounds:{roundName:{label,type,side,Opponent:{id,code},Room,Judges,Results:{judgeId:{winloss:"W"|"L"}},bye,forfeit}}}`. Completed rounds only; 401 if the event is anonymous.
- `GET /rest/tourns/{tournId}/schedule` → rounds with `name,label,type,published,startTime,Event{id,name,abbr,type}`.
- `GET /rest/tourns/{tournId}/events/{abbr}/field` → `{name,id,Entries:[{id,name,code,active,waitlist,School{name},Students[{firstName,lastName}]}]}`.

## Review Focus
1. Tabroom returns 503 HTML (maintenance): the entry screen shows the last good copy plus a banner, never a crash. Tested in cache.test.js.
2. Round published but the entry isn't in it (bye or dropped): the round shows "Bye" or "Not in this round", and the next round still resolves. Tested in tabroom.test.js.
3. An anonymous event (records 401): records are skipped and pairings are still shown. Tested in tabroom.test.js.
4. A field with an odd number of teams, and break size ≥ field: break math handles byes and caps. Tested in breakmath.test.js.
5. A pasted Tabroom URL or bare ID in the search box: the ID is extracted from `tourn_id=`. Tested with the hub page's parser in tabroom.test.js (`parseTournId`).

---

### Task 1: Break math module
**Files:** Create `deploy/worker/hub/breakmath.js`, `deploy/worker/package.json`, `deploy/worker/test/breakmath.test.js`.
**Produces:** `simulate({field, prelims, breakSize, done=0, wins=null, me=null, myWins=null, sims=10000, seed=1}) -> {byWins:{k:{p,n}}, safe, bubble:[k], myChance|null}`; `defaultBreak(field)`.
- [ ] Tests: seeded determinism; 64/6/16 gives safe 5, bubble contains 4; 24/4/4 is monotonic; an odd field and breakSize ≥ field (everyone clears).
- [ ] Implement a mulberry32 PRNG; rounds < 2 random, then sort by wins (random tiebreak) and pair adjacent; an odd field gives the last team a bye (win); coin-flip results; the break takes the top breakSize by wins with random tiebreak.
- [ ] `node --test test/` passes; commit.

### Task 2: Tabroom client and mappers
**Files:** Create `deploy/worker/hub/tabroom.js`, `deploy/worker/test/tabroom.test.js`, `deploy/worker/test/fixtures/*.json`.
**Produces:** `tabroomGet(path, fetchImpl)`, `mapTourn`, `mapUpcoming`, `mapSchedule`, `mapField`, `entryView({schedule, field, schematics, records, entryId, abbr})`, `parseTournId(text)`, `class TabroomDown`.
- [ ] Tests on fixtures: field mapping, entry view (current round, side label Pro/Con, opponent, judges with personId, W/L from records, bye round, not paired yet), anonymous records (null), `parseTournId`, maintenance HTML → TabroomDown.
- [ ] Implement; tests pass; commit.

### Task 3: Cache layer and hub routes
**Files:** Create `deploy/worker/hub/cache.js`, `deploy/worker/hub/routes.js`, `deploy/worker/test/cache.test.js`; modify `deploy/worker/worker.js`, `deploy/worker/wrangler.toml`.
**Produces:** `cached({cache, kv, ctx, key, ttl, persist, fetcher}) -> {data, asOf, stale}`; `handleHub(request, env, ctx) -> Response|null`.
- [ ] Tests: hit, miss then store, failure with a KV copy → stale, failure without one → throws, a failure is negatively cached for 20 s, KV written only when the value changed.
- [ ] Routes `/t/api/upcoming`, `/t/api/tourn/:id`, `/t/api/tourn/:id/field/:abbr`, `/t/api/tourn/:id/event/:abbr/entry/:entryId`; pages `/`, `/t/*`, `/break` → hub.html; `/hub/breakmath.js`; `/cards` → app.html; `/app` → 301 `/cards`; `/about` → landing.html.
- [ ] Create the KV namespace `HUB_KV` and bind it; commit.

### Task 4: Hub page
**Files:** Create `deploy/worker/hub.html`; modify `deploy/worker/app.html` and `landing.html` links (`/app` → `/cards`).
- [ ] Home (search, this weekend, followed), tournament (schedule, events, field with Follow), entry screen (current round, record, break meter, opponent and judge cards, 60 s refresh while visible, stale banner), `/break` calculator. Dark mode, 16 px gutters, no horizontal scroll.
- [ ] Extension bridge: `postMessage` `pfhub-req`/`pfhub-res`; the judge card shows paradigm summary heuristics when the extension answers.
- [ ] Check the pages in a browser (wrangler dev), including with Tabroom mocked down; commit.

### Task 5: Chrome extension
**Files:** Create `extension/manifest.json`, `extension/background.js`, `extension/content.js`, `extension/README.md`.
- [ ] MV3, permissions `cookies`; host permissions for api.tabroom.com, www.tabroom.com, api.opencaselist.com and debate.peshcompsci.org. Ops: `paradigm(personId)`, `judgeRecord(personId)`, `caselistSearch(q)`. Validate args; answer only our origin.
- [ ] README with unpacked-install steps; commit.

### Task 6: Ship
- [ ] Add `node --test` to CI; run all tests; `npx wrangler deploy`; live smoke on `/`, `/t/40176`, `/t/api/upcoming`, `/cards`; update the README and the landing link; push.
