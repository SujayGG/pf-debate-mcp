# Hosting runbook: the free public server

```
student's AI app ──▶ debate.peshcompsci.org (Cloudflare Worker, deploy/worker)
                         ├─ /            landing page
                         ├─ /mcp         health-gated proxy ─────────┐
                         └─ /health /stats /files/…  proxy ──────────┤
                                                                     ▼
                 Hugging Face Space SujayG5/pf-debate (deploy/space, Docker, free CPU)
                 `pf-debate-mcp serve-http`, ONE process, stateless HTTP
                 library downloaded at boot from dataset SujayG5/pf-debate-library
```
Cost: $0. This uses the Cloudflare Workers free plan, the Hugging Face Spaces free CPU tier, and free GitHub Actions.

## One-time setup
1. **Hugging Face:**
   - Create a write token.
   - Create the Space `SujayG5/pf-debate` (SDK: Docker, hardware: CPU basic, visibility: public).
   - Publish the library once: `hf auth login`, then `uv run python scripts/publish_library.py --version 1 --upload`.
2. **Cloudflare:**
   - The `peshcompsci.org` zone must be on the account.
   - Create an API token with the "Edit Cloudflare Workers" template, scoped to the account and the zone.
   - Note the account ID.
3. **GitHub repo secrets:** add `HF_TOKEN`, `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` (Settings → Secrets and variables → Actions).
4. Push a version tag (`git tag v0.4.0 && git push --tags`). The `deploy` workflow tests, pushes the Space, deploys the Worker, and smoke-tests `https://debate.peshcompsci.org`.

## Routine operations
| Task | How |
|---|---|
| Deploy | Push a tag `vX.Y.Z` (bump the versions in pyproject.toml, manifest.json and .claude-plugin/plugin.json first). |
| Roll back | Actions → deploy → Run workflow with an older tag, or run `npx wrangler rollback` in deploy/worker for the Worker alone. |
| Pause tool traffic | Set `KILL_SWITCH = "on"` in deploy/worker/wrangler.toml and run `npx wrangler deploy`. The landing page stays up. |
| Move the backend | Change `BACKEND_URL` in wrangler.toml and deploy the Worker. Students keep the same URL. The new host must run `pf-debate-mcp serve-http` with `ALLOWED_HOSTS` including its own host name. |
| New library version | Run `scripts/publish_library.py --version N+1 --upload`. Spaces pick it up on the next restart; local users on `build_library`. |
| Rotate tokens | Create a new HF/Cloudflare token, update the repo secret, and revoke the old one. |
| Check usage | Open `https://debate.peshcompsci.org/stats` (counts only; no queries or content are ever logged). |

## When the nightly check opens an issue
1. Open `https://debate.peshcompsci.org/health`.
   - **503 "waking up"**: the Space was asleep. Wait 2 minutes and recheck. If it happens often, check that the Worker cron is running (Cloudflare dashboard → Workers → pf-debate → Triggers).
   - **Space error**: open the Space logs on Hugging Face.
     - If the library download failed, restart the Space.
     - If the dataset is missing, re-run the publish step.
2. `/stats` shows `calls_today` at a budget in `metrics.BUDGETS`: someone may be abusing it. Either raise the budget (if the CPU copes), turn on the kill switch, or start the sign-in TODO.

## Rules that must not change
- **One process only** (`WEB_CONCURRENCY=1`). Cuts live in process memory, so a second worker process would make ids randomly unknown. The server refuses to start otherwise.
- `ALLOWED_HOSTS` must list every public host name. The MCP SDK rejects any other Host header, by design.
- Never add the caselist tools to hosted mode. They need each student's own Tabroom login.

## Fetch-success gate (decides whether audit_evidence runs hosted)
Run `uv run python scripts/fetch_gate.py --n 50` from a datacenter IP (a GitHub Actions run or the Space itself) and record the result below.

| Date | Where | Result |
|---|---|---|
| 2026-09-24 | home connection (residential IP), 30 PF cites from 2020+ | 8/30 (26%): 16 HTTP errors (bot blocks like Forbes/WSJ, dead links), 5 paywalls, 1 unreachable. The Wayback availability API found 0/22 snapshots (unverified; possibly throttled). **Decision: audit_evidence stays local-first; the hosted version waits for a datacenter-IP run.** |
