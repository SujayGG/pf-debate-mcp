"""Build the no-terminal downloads into dist/ (attached to GitHub Releases).

  pf-debate.mcpb          Claude Desktop one-click extension (full tools)
  pf-debate-skill.zip     Claude.ai skill upload (knowledge only)
  pf-debate-guide.md      one knowledge file for ChatGPT / Gemini / Claude Projects
  instructions.md         paste-in instructions for those apps

Run: uv run python scripts/package.py   (needs Node for `npx @anthropic-ai/mcpb`)
"""

import json
import re
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "src" / "pf_debate_mcp" / "skills"
DIST = ROOT / "dist"
TASKS = ["pf-case", "pf-cut-card", "pf-analyze", "pf-blocks", "pf-scout"]


def versions_match() -> str:
    v = {
        "pyproject.toml": tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"],
        "manifest.json": json.loads((ROOT / "manifest.json").read_text())["version"],
        ".claude-plugin/plugin.json": json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"],
    }
    assert len(set(v.values())) == 1, f"version mismatch: {v}"
    return next(iter(v.values()))


def body(md: Path) -> str:
    """Markdown without YAML frontmatter."""
    return re.sub(r"\A---\n.*?\n---\n", "", md.read_text(encoding="utf-8"), flags=re.S).strip()


def main() -> None:
    version = versions_match()
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir()

    subprocess.run(["npx", "-y", "@anthropic-ai/mcpb", "pack", str(ROOT), str(DIST / "pf-debate.mcpb")],
                   check=True, shell=(shutil.which("npx") or "").lower().endswith(".cmd"))

    # Claude.ai: one skill folder; task skills ride along as <name>.md files next to SKILL.md.
    with zipfile.ZipFile(DIST / "pf-debate-skill.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in (SKILLS / "pf-debate").rglob("*.md"):
            z.write(f, "pf-debate/" + f.relative_to(SKILLS / "pf-debate").as_posix())
        for t in TASKS:
            z.writestr(f"pf-debate/{t}.md", body(SKILLS / t / "SKILL.md") + "\n")

    # ChatGPT / Gemini / Claude Projects: a single knowledge file (Gems cap the file count).
    parts = [f"# PF Debate Guide (pf-debate-mcp v{version})", body(SKILLS / "pf-debate" / "SKILL.md")]
    parts += [f"<!-- guide: {t} -->\n" + body(SKILLS / t / "SKILL.md") for t in TASKS]
    parts += [f"<!-- reference: {f.stem} -->\n" + body(f)
              for f in sorted((SKILLS / "pf-debate" / "references").glob("*.md"))]
    (DIST / "pf-debate-guide.md").write_text("\n\n---\n\n".join(parts) + "\n", encoding="utf-8")
    shutil.copy(ROOT / "chat" / "instructions.md", DIST / "instructions.md")

    for f in sorted(DIST.iterdir()):
        print(f"{f.name:24} {f.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
