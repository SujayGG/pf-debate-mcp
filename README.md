# pf-debate-mcp

A Public Forum debate partner for your own AI agent (Claude Code, Claude Desktop, Cursor, Codex, or any MCP host). Ask it things like:

- "Make me a neg case on the Sep/Oct topic centered around a nuclear impact."
- "Cut me a card that data centers raise residential electricity bills."
- "Analyze this card and give me CX questions." / "Write blocks to their econ contention."
- "They dropped our link turn. Write my summary."
- "Scout Lexington AB on the caselist."

Your agent does the thinking on **your** plan, so there are no per-site token limits. This package gives it:

| Tool | What it does |
|---|---|
| `search_cards` / `get_card` | A local library of cut cards from [OpenCaselist](https://huggingface.co/datasets/Yusuf5/OpenCaselist) (PF, LD, Policy and camp files, 2013–2024), full-text search, "popular" ranking by how many teams read a card |
| `fetch_source` | Any article or PDF, turned into clean paragraphs plus citation metadata |
| `cut_card` | Cuts a card, with an **ethics gate**: the body, underlining and highlighting must match the source verbatim or the cut is rejected. NSDA-complete citations. |
| `export_doc` | A Verbatim-compatible .docx (Pocket/Hat/Block/Tag, underline, highlight) |
| `caselist_search` / `caselist_team` / `caselist_download` | OpenCaselist with your Tabroom login: round reports, cites, open-source docs imported as cards |
| `library_status` | Whether the library is built |

It also ships six skills: pf-debate (jargon, format, tactics, impacts, evidence ethics), pf-cut-card, pf-analyze, pf-case, pf-blocks and pf-scout. Hosts without skill support get them as MCP prompts and resources.

Web search comes from your agent's own search tool.

## Install

Requires [uv](https://docs.astral.sh/uv/).

**Claude Code (plugin: server + skills):**
```
/plugin marketplace add SujayGG/pf-debate-mcp
/plugin install pf-debate@pf-debate
```

**Any other MCP host.** Add this to its MCP config (Claude Desktop `claude_desktop_config.json`, Cursor `.cursor/mcp.json`, and so on):
```json
{
  "mcpServers": {
    "pf-debate": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/SujayGG/pf-debate-mcp", "pf-debate-mcp"]
    }
  }
}
```

**One-time setup (in a terminal):**
```
uvx --from git+https://github.com/SujayGG/pf-debate-mcp pf-debate-mcp build-library           # full library (~1 h, resumable)
uvx --from git+https://github.com/SujayGG/pf-debate-mcp pf-debate-mcp build-library --quick   # PF cards only, a few minutes
uvx --from git+https://github.com/SujayGG/pf-debate-mcp pf-debate-mcp login                   # optional: OpenCaselist via Tabroom
```
- The default build keeps every PF and OpenEv card, plus LD/Policy cards read by 5 or more teams (`--min-reads`). See `build-library --help`.
- If a build is interrupted, rerun it. Finished shards are skipped.
- The login stores only the session cookie, never your password. You can also set `TABROOM_USERNAME` and `TABROOM_PASSWORD`.

Data lives in `~/.pf-debate/` (set `PF_DEBATE_HOME` to move it). Exports go to `~/Documents/pf-debate/` (`PF_DEBATE_EXPORTS`).

## Evidence ethics
Cards are never generated. `cut_card` stores only exact slices of fetched source text, and the skills forbid writing card text from memory. You are still responsible for reading your evidence in context and following NSDA evidence rules.

## Development
```
uv run pytest
uv run pf-debate-mcp            # stdio server
npx @modelcontextprotocol/inspector uv run pf-debate-mcp
```

Card data: OpenCaselist dataset (MIT) by the debate community via openCaselist. Code: MIT.
