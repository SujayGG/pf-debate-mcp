# pf-debate: MCP server + skills for Public Forum prep

## Context
Tools like DebateCard AI (card cutting modes Snipe/Auto/Agent, Logos card library, block builder, Speechify, debater search) run on the site's own LLM API budget, so users hit token limits. Goal: a standalone, one-time install that lets a PF debater's **own agent** (Claude Code, Claude Desktop, Cursor, Codex — any MCP host) do the same work conversationally: "build me an aff case on the Sep/Oct topic" leads to real, ethically cut cards from the largest card corpus plus the live web, exported as a speech doc.

Decisions so far:
- Public, any-MCP-agent use.
- Conversational, not an app UI.
- Architecture: one local MCP server plus portable skills. The agent does all reasoning. The server provides data access, verbatim-verified card cutting and .docx output.

Research facts the design relies on:
- **OpenCaselist dataset** (HF `Yusuf5/OpenCaselist`, MIT): 4.8M cards, 2013–2024, Policy/LD/PF, parquet (~27–54 GB). Columns include `tag, cite, fullcite, summary(underlined), spoken(highlighted), fulltext, markup(HTML), pocket/hat/block, side, year, event, level, bucketId(dedup), caselistName, schoolId, teamId`.
- **OpenCaselist API** `https://api.opencaselist.com/v1`: `POST /login {username,password,remember}` (Tabroom creds) returns cookie `caselist_token`. Endpoints: `GET /caselists`, `/caselists/{c}/schools/{s}/teams/{t}/rounds|cites`, `GET /search?q=&shard=`, `GET /download?path=`.
- **NSDA evidence rules:** full cite (author, quals, date, title, publication, URL, access date). Text must be verbatim and retrievable, with the read portions marked (underline/highlight). Paraphrase is held to the same accuracy standard.
- Current topic (Sep/Oct 2026): *"Resolved: The USFG should enact a moratorium on hyperscale data center construction."* Use it as the end-to-end test case.

## Design

### Repo: `C:\Users\sujay\pf-debate-mcp` (Python 3.11+, `uv`)
```
pyproject.toml            # deps: mcp, httpx, trafilatura, pypdf, python-docx, duckdb
.claude-plugin/plugin.json + marketplace.json   # Claude Code: /plugin install gets server+skills
.mcp.json                 # {"pf-debate": {"command":"uvx","args":["pf-debate-mcp"]}}
src/pf_debate/
  server.py    # FastMCP: tools below + each skill exposed as an MCP prompt + server instructions
  library.py   # build-library (duckdb reads hf:// parquet, filter event=PF, dedupe by bucketId) -> SQLite FTS5; search
  sources.py   # fetch URL/PDF -> clean text, numbered paragraphs, metadata (author/date/title/site); cache in pf.db
  cards.py     # cut_card: verbatim verification + storage
  docx_io.py   # export Verbatim-style .docx; parse .docx (caselist downloads) into cards
  caselist.py  # OpenCaselist client (login, search, team rounds/cites, download)
  cli.py       # `pf-debate-mcp` (serve) | `build-library [--events PF] [--since 2018] [--limit N]` | `login`
  skills/pf-debate/SKILL.md + references/{glossary,format,tactics,impacts,evidence-ethics}.md
  skills/pf-cut-card, pf-analyze, pf-case, pf-blocks, pf-scout (SKILL.md each)
tests/test_cards.py, tests/test_docx_io.py
```
Data dir `~/.pf-debate/`: `library.db` (read-only corpus, rebuildable), `pf.db` (fetched sources + user's cut cards), `token` (caselist cookie, file perms user-only). Exports go to `~/Documents/pf-debate/`.

### MCP tools (9)
| Tool | Does |
|---|---|
| `search_cards(query, scope="library"\|"mine", year_from?, side?, sort="relevance"\|"popular", limit=10)` | FTS5 bm25 over tag/cite/pocket/hat/block/highlighted/fulltext. Headings are included so a query like "nuclear war impact" also hits impact blocks. `popular` ranks by `duplicateCount` (cards many teams read), a quality proxy. Returns id, tag, short cite, snippet, year, school, times read |
| `get_card(id)` | Full card: tag, fullcite, text with underline/highlight marks |
| `fetch_source(url)` | HTML (trafilatura) or PDF (pypdf) turned into `source_id`, metadata, numbered paragraphs. Clear error for paywalls/blocked pages |
| `cut_card(source_id, tag, cite{author,quals,date,title,publisher,url}, start_quote, end_quote, underline[], highlight[])` | **Ethics gate.** The body is the exact source text from `start_quote` to the end of `end_quote`. Every underline/highlight string must appear verbatim inside the body. Only whitespace and curly/straight quotes are normalized. Rejects anything else and says what didn't match. Warns on missing date/author/quals, on highlight outside underline, and on a body under ~2 sentences (context). `source_id` may also be a library/caselist card (recut) |
| `export_doc(title, items[{pocket\|hat\|block\|analytic: text} \| {card: id}], filename)` | Writes .docx using Verbatim style names (Pocket/Hat/Block/Tag = Heading 1–4, bold cite, underline style, highlight) so it opens cleanly in Verbatim/Word |
| `caselist_search(query)` | `/search` on the current HS PF caselist |
| `caselist_team(school, team, caselist?)` | Rounds (reports, opponents, open-source paths) plus cites. Defaults to the latest HS PF caselist |
| `caselist_download(path)` | Downloads an open-source .docx and parses it into addressable cards |
| `library_status()` | Whether the corpus is built, its size and years, and the build command if missing |

Deliberately not included: a web search tool. The host agent's own search (Claude WebSearch, Cursor, etc.) finds URLs, and `fetch_source` + `cut_card` take over from there.

### Skills: the agent as a full PF partner (Agent Skills `SKILL.md`; the same files are served as MCP prompts and resources for hosts without skills)
Knowledge lives in one place, `skills/pf-debate/references/*.md`. Skills load these files on demand, so a jargon-heavy request like "make me a case centered around a nuclear impact" or "they dropped our link turn, write the summary" is understood correctly.

- **pf-debate** (core, always relevant: partner persona + router). References:
  - `glossary.md`: PF/circuit jargon. Examples: uniqueness/NUQ, link, internal link, impact, terminal impact, link turn vs. impact turn, delink, mitigation, defense vs. offense, frontline, block, extend, dropped/conceded, collapse, sticky defense, turns case, link-in, pre-req, short-circuit, clarity of impact. Also: magnitude/probability/timeframe/scope/reversibility weighing, meta-weighing, framework, contention, sub-point, off-time roadmap, signposting. Evidence terms: tag/cite/card/powertag/highlighting/underlining, speech doc, email chain, disclosure, open source, OpenEv, paraphrase theory, IVI, theory/shell, K, lay/flow/tech judge.
  - `format.md`: speech order and times, what each speech must do (1st vs. 2nd speaking position), crossfire rules, prep, evidence exchange norms.
  - `tactics.md`: collapse strategy, weighing that actually wins, frontlining, time allocation per speech, crossfire question banks and traps, turns strategy, judge adaptation (lay vs. flow vs. tech/progressive).
  - `impacts.md`: common terminal impacts and their standard link chains, with the weighing each wins on. Covers nuclear war (great-power conflict, US–China/Taiwan, Russia/NATO, India–Pakistan, prolif, escalation), extinction, climate, economy/recession (and its link into war), poverty/structural violence, disease/pandemics, AI risk, democracy. Includes the typical counter-responses to each.
  - `evidence-ethics.md`: NSDA rules (full cite with quals, verbatim, no out-of-context cuts, highlighting can't change meaning, paraphrase standard, evidence challenges).
- **pf-cut-card**: Cutting workflow and quality bar.
  - Workflow: `search_cards`, then host web search, then `fetch_source`, then `cut_card`.
  - Targets: about 30–50% underlined, 10–25% highlighted; highlighted text reads as a sentence; the tag must be supported by the highlight.
- **pf-analyze**: Analyze any card or case (the user's, a library card, or an opponent's caselist doc).
  - Checks: tag vs. highlight strength (powertagging), cite/quals/date quality, missing warrants, gaps in the link chain, impact calculus, and what the unhighlighted text concedes (indicts).
  - Outputs: a rating, CX questions to ask, and responses/blocks to it.
- **pf-case**: Case building.
  - Standard mode: topic analysis, then propose 1–3 contentions.
  - **Impact-first mode** ("centered around a nuclear impact"): find strong terminal-impact cards first (`search_cards(..., sort="popular")`), build the internal-link chain backward to the resolution, then find uniqueness.
  - Always **confirm the contention plan with the user**, then cut/pull cards, write the constructive to speech length (4 min ≈ 750–850 words), pre-write weighing, then `export_doc`.
- **pf-blocks**: Frontlines and blocks (turns, defense, delinks, NUQ), plus rebuttal/summary/final focus writing. Enforces extension rules: 2nd rebuttal frontlines, and summary must extend whatever final focus goes for.
- **pf-scout**: Topic dashboard (definitions, burdens, likely aff/neg args with their best impacts, a prep plan) and opponent scouting (`caselist_team`, then `caselist_download`, then pf-analyze, then a block list).

### Install paths
- Any MCP host: `uvx pf-debate-mcp` in its config (README gives snippets for Claude Desktop, Cursor, Codex). Then run once: `uvx pf-debate-mcp build-library` and, optionally, `uvx pf-debate-mcp login`. Credentials can also come from env vars `TABROOM_USERNAME` / `TABROOM_PASSWORD`. The password is never stored; only the cookie is.
- Claude Code: `/plugin marketplace add <github repo>`, then `/plugin install pf-debate`.

## Build order (runs autonomously after approval; pauses only for Tabroom credentials and for publishing)
1. Scaffold package + `cli.py` serve stub; confirm it connects via MCP Inspector.
2. `sources.py` + `cards.py` + tests (the ethics gate is the core; TDD).
3. `docx_io.py` export + parse + round-trip test.
4. `library.py`. First inspect real `event`/`level` values and PF row count with a duckdb query, then build with `--limit` for dev, then the full PF build (record size and time in the README).
5. `caselist.py` (needs the user's Tabroom login for a live check).
6. The six skills and their references (the glossary, tactics and impacts files are the biggest writing job; research is grounded in NSDA rules and circuit norms), plus MCP prompts, resources and instructions.
7. Plugin manifest, README, end-to-end run on the data-center topic.
8. Publish to GitHub/PyPI **only after the user OKs it** (public, outward-facing).

## Verification
- `uv run pytest`:
  - `cut_card` rejects a changed word, an invented sentence, and a highlight outside the body.
  - It accepts smart-quote/whitespace differences.
  - A docx export, then parse, keeps tag, cite, underline and highlight.
- `npx @modelcontextprotocol/inspector uv run pf-debate-mcp`: call each tool by hand.
- `build-library --limit 5000`, then `search_cards("data center water usage")` returns relevant cards.
- End-to-end in Claude Code: "Build me an aff case on the Sep/Oct PF topic with cut cards, export a speech doc."
  - The .docx opens in Word with correct styles.
  - Spot-check 3 cards verbatim against their URLs.
- Caselist: log in, then `caselist_team` on a known PF team returns rounds and cites.
- Knowledge check (run in a fresh agent with only the plugin loaded; answers must be correct and use jargon naturally):
  - "Difference between a link turn and an impact turn, and why you can't read both on the same arg?"
  - "Make me a neg case centered around a nuclear impact": it should produce a chain like moratorium → AI lead/China → Taiwan → nuclear war, sourced with real cards, plus weighing.
  - "Analyze this card": paste a powertagged card; it should flag the powertag and write CX questions.

## Risks / non-goals
- The corpus stops at 2024, so current-topic evidence comes mostly from the web and the caselist. Much older PF evidence in the corpus was paraphrased or has thin cites; show `year` and let the skill prefer recent cards.
- Full-corpus scan size and time are unknown until step 4 (it could be tens of GB streamed once).
- Paywalled sources can't be fetched. The agent skips to another source; it never cuts from memory.
- Caselist use follows its terms: personal use with the user's own login, and the built-in rate limits are respected.
- Out of scope for v1: web UI, bracket math, a bundled web search, vector embeddings, Google Docs export, LD/Policy-specific skills (the `--events` flag still allows those corpora).
