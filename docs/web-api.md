# Web app API (contract)

The web app (`/app`, a static page served by the Cloudflare Worker) talks to the Space through the Worker, under `/api/*`. It uses the same functions and the same verbatim gate as the MCP tools. Errors come back as `{"error": "<readable message with a next step>"}` with a 4xx/5xx status. Rate limits are per client IP (web traffic comes from students' own IPs): about 120 requests per minute generally and 20 per minute for `/api/llm`. When a limit trips, the response is 429 `{"error": ...}`.

## Cards and sources (Layer 1, no AI)
| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/search` | `q`, `mode=hybrid\|keyword` (default hybrid), `sort=relevance\|popular`, `side=A\|N`, `event=pf\|ld\|cx\|openev`, `year_from`, `limit` (≤30) | `{"results": [{id, tag, cite, year, event, side, times_read, headings, highlighted}]}` |
| GET | `/api/card/{id}` | `view=read\|full` | `{id, tag, cite_short, cite_rest, runs: [[text, underlined, highlighted], ...], times_read?, origin}` |
| GET | `/api/find` | `q`, `kinds=papers,news` (default both), `limit` | `{"results": [{kind: "paper"\|"news", title, url, authors: [..], quals: "affiliations or null", date, source, snippet, pdf_url?}], "skipped": ["gdelt: timeout", ...]}` |
| POST | `/api/fetch` | `{url}` | `{source_id, meta: {url, title, author, date, publisher}, paragraphs: ["...", ...]}` |
| POST | `/api/suggest` | `{source_id, claim}` | `{paragraph, start_quote, end_quote, highlight: [..], underline: [..], score}`. It passes cut_card as-is. |
| POST | `/api/cut` | `{source_id, tag, author, date, title, publisher, url, quals, start_quote, end_quote, highlight: [..], underline?: [..], paragraph?}` | `{card: {id, tag, cite_short, cite_rest, runs}, warnings: [..]}`; a non-verbatim cut returns 422 `{"error": "REJECTED ..."}` |
| POST | `/api/export` | `{title, items: [{pocket\|hat\|block\|tag\|text: str} \| {card: id}], format: "docx"\|"gdocs"}` | The file itself (`Content-Disposition: attachment`) |

Card ids: `lib:N` for library cards, `c_xxxxxxxxxxxx` for hosted cuts (these last until the server restarts or memory fills). `source_id` values look like `s_xxxxxxxxxxxx`.

## Chat (Layer 2)
The browser runs the agent loop, so it works the same with either model source:
- **Shared free pool** (no sign-in): `POST /api/llm` with `{messages, tools}` (OpenAI chat format). It returns `{message, provider}` (an OpenAI assistant message, possibly with `tool_calls`), or 429 `{"error": "The free AI pool is used up for today", "exhausted": true}`.
- **Puter** (user signed in): `puter.ai.chat(messages, {tools})` in the browser. The student's own free allowance pays.

The tools the model can call: `GET /api/tools` returns the MCP tools as OpenAI function schemas (hosted set: search_cards, get_card, find_sources, fetch_source, suggest_cut, cut_card, export_doc, pf_guide, library_status). The browser executes a call with `POST /api/tool/{name}` and body `{arguments}`. The response is `{"content": "<text the MCP tool returns>", "is_error": bool}`. The system prompt comes from `GET /api/system` as `{"prompt": "..."}`: the server instructions plus the pf-debate skill.

**Hand-off** (always available, needs no server): the browser builds a prompt from `/api/system` plus the selected cards' text and cites. It opens `https://chatgpt.com/?q=<prompt>` when the prompt is under 6,000 characters; otherwise it copies the prompt to the clipboard and opens chatgpt.com or gemini.google.com.

## Health
`GET /health` and `GET /stats`, as before.
