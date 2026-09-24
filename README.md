# pf-debate-mcp

A Public Forum debate partner for the AI you already use. Ask it things like:

- "Make me a neg case on the Sep/Oct topic centered around a nuclear impact."
- "Cut me a card that data centers raise residential electricity bills."
- "Analyze this card and give me CX questions." / "Write blocks to their econ contention."
- "They dropped our link turn. Write my summary."
- "Scout Lexington AB on the caselist."

It knows PF jargon, speech times, tactics, weighing and the standard impact chains. It never makes up evidence.

## Free web app (any age, no account)
**https://debate.peshcompsci.org/app** runs entirely in your browser:
- plain-English search of about 173k cut cards
- finding new papers and news
- auto-suggested cuts with click-to-adjust highlighting and the verbatim check
- a doc builder that exports to Word or Google Docs
- an AI chat, powered by a free shared pool, your own free Puter account, or a one-click hand-off to your ChatGPT/Gemini

## Pick your app (no terminal needed)

| App | What you get | Setup |
|---|---|---|
| **Claude Desktop** (Mac/Windows) | Everything: the card library, verbatim card cutting, caselist scouting, Word speech docs | [One-click install](#claude-desktop-one-click) |
| **Claude.ai** (web/mobile) | PF knowledge + card cutting with Claude's web search | [Upload a skill](#claudeai-web) |
| **ChatGPT** | PF knowledge + card cutting with ChatGPT's web search | [Make a GPT or Project](#chatgpt) |
| **Gemini** | PF knowledge + card cutting with Gemini's web search | [Make a Gem](#gemini) |
| Claude Code, Cursor, other MCP apps | Everything | [Developer install](#developer-install) |

**What "full tools" adds.** The Claude Desktop and developer installs give your AI a local library of already-cut cards and a card cutter. The cutter checks every word against the real article and **rejects anything that isn't verbatim**, so fabricated evidence can't slip in. Web chat apps can't run local tools. There, the AI cuts cards from pages it opens, and you should check each card against its link before reading it.

All downloads are on the **[latest release page](https://github.com/SujayGG/pf-debate-mcp/releases/latest)**.

### Claude Desktop (one click)
1. Install [Claude Desktop](https://claude.ai/download) if you don't have it.
2. Download **[pf-debate.mcpb](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/pf-debate.mcpb)**.
3. Double-click the file (or drag it into Claude Desktop → Settings → Extensions), then click **Install**.
   - The Tabroom email and password fields are optional. They are only for OpenCaselist scouting, and Claude Desktop stores them securely.
4. In a new chat, say: **"Build the quick card library."** This takes a few minutes, runs in the background, and gets about 6k PF cards. Then say **"build the full card library"** for about 170k cards, including the most-read Policy/LD impact cards (nuke war, econ, heg). That takes a few hours and about 0.8 GB, and it resumes if interrupted.
5. Start prepping. Speech docs are saved to `Documents/pf-debate/`.

### Claude.ai (web)
1. Download **[pf-debate-skill.zip](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/pf-debate-skill.zip)**.
2. On claude.ai: **Settings → Capabilities**. Turn on **Code execution** (skills need it) and **Web search**, then under **Skills** click **Upload skill** and choose the zip.
3. Ask any PF question. Claude loads the skill automatically.

Alternative: create a **Project**, paste [instructions.md](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/instructions.md) into the project instructions, and upload [pf-debate-guide.md](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/pf-debate-guide.md) as project knowledge.

### ChatGPT
Download **[instructions.md](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/instructions.md)** and **[pf-debate-guide.md](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/pf-debate-guide.md)**. Then use either option:
- **Custom GPT** (needs a paid plan to create; anyone can use a shared one):
  1. Explore GPTs → **Create** → **Configure**.
  2. Paste instructions.md into **Instructions** and upload pf-debate-guide.md under **Knowledge**.
  3. Turn on **Web Search**.
  4. Save it. Share the link with your team so they need no setup.
- **Project** (any plan with Projects): New project → **Instructions**: paste instructions.md → **Files**: add pf-debate-guide.md.

### Gemini
1. Download the same two files ([instructions.md](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/instructions.md), [pf-debate-guide.md](https://github.com/SujayGG/pf-debate-mcp/releases/latest/download/pf-debate-guide.md)).
2. gemini.google.com → **Gems** → **New Gem**. Paste instructions.md into **Instructions** and add pf-debate-guide.md under **Knowledge**. Save it.
3. You can share the Gem with teammates.

## Tools (Claude Desktop / MCP installs)
| Tool | What it does |
|---|---|
| `pf_guide` | PF knowledge: glossary, format, tactics, impacts, evidence ethics, how to build cases/blocks/scouts |
| `search_cards` / `get_card` | Plain-English or keyword search (meaning + keywords) over the local library of about 173k cut cards from [OpenCaselist](https://huggingface.co/datasets/Yusuf5/OpenCaselist) (PF, LD, Policy, camp files; 2014–2022), with "popular" ranking by how many teams read a card |
| `find_sources` | New evidence: recent papers (author affiliations for quals, free PDFs) and current news. Free, no API keys |
| `fetch_source` | Any article or PDF, turned into clean paragraphs plus citation metadata |
| `suggest_cut` | Proposes the best passage and highlights for your claim (exact source text) |
| `cut_card` | Cuts a card; the text must match the source verbatim or it's rejected. Full NSDA citations. |
| `export_doc` | A Verbatim-compatible .docx (Pocket/Hat/Block/Tag, underline, highlight), or `format="gdocs"` for a Google-Docs-ready page |
| `caselist_search` / `caselist_team` / `caselist_download` | OpenCaselist with your Tabroom login: round reports, cites, open-source docs as cards |
| `build_library` / `library_status` | Build the card library in the background and check its progress |

Skills: pf-debate, pf-cut-card, pf-analyze, pf-case, pf-blocks, pf-scout (in `src/pf_debate_mcp/skills/`).

## Developer install
Requires [uv](https://docs.astral.sh/uv/).

**Claude Code (plugin: server + skills):**
```
/plugin marketplace add SujayGG/pf-debate-mcp
/plugin install pf-debate@pf-debate
```

**Any MCP host (Cursor, Codex, Windsurf, and others):**
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

**Terminal commands** (optional; the `build_library` tool does the same from chat):
```
uvx --from git+https://github.com/SujayGG/pf-debate-mcp pf-debate-mcp build-library           # full library (a few hours, resumable)
uvx --from git+https://github.com/SujayGG/pf-debate-mcp pf-debate-mcp build-library --quick   # PF cards only, a few minutes
uvx --from git+https://github.com/SujayGG/pf-debate-mcp pf-debate-mcp login                   # OpenCaselist via Tabroom
```
- The full build keeps every PF and OpenEv card, plus LD/Policy cards read by 5 or more teams (`--min-reads`).
- The login stores only the session cookie, never your password. You can also set `TABROOM_USERNAME` and `TABROOM_PASSWORD`.
- Data lives in `~/.pf-debate/` (`PF_DEBATE_HOME`). Exports go to `~/Documents/pf-debate/` (`PF_DEBATE_EXPORTS`).

## Evidence ethics
With the tools, cards are never generated: `cut_card` stores only exact slices of fetched source text. In web chat apps, the instructions forbid writing card text from memory, but nothing checks it automatically. Verify every card against its source. You are responsible for following NSDA evidence rules.

## Development
```
uv run pytest
uv run pf-debate-mcp                         # stdio server
uv run python scripts/package.py             # build the release downloads into dist/
npx @modelcontextprotocol/inspector uv run pf-debate-mcp
```
Releasing: bump the version in `pyproject.toml`, `manifest.json` and `.claude-plugin/plugin.json`. Then run `package.py` and `gh release create vX.Y.Z dist/*`.

Card data: the OpenCaselist dataset (MIT), from the debate community via openCaselist. Code: MIT.
