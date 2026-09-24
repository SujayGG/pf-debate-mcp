# Hosting runbook: the free public server

```
student ──▶ debate.peshcompsci.org (Cloudflare Worker, deploy/worker: landing, /app, proxy)
                 │  Workers VPC binding "BACKEND" (no public origin, no open ports)
                 ▼
          Cloudflare Tunnel "pf-debate" (cloudflared on the maintainer's PC)
                 ▼
          pf-debate-mcp serve-http on 127.0.0.1:7860 (ONE process, stateless HTTP)
          library: ~/.pf-debate (download: SujayG5/pf-debate-library on Hugging Face)
```
Cost: $0 (Cloudflare Workers free plan, Workers VPC, Cloudflare Tunnel, Hugging Face datasets, GitHub Actions).
Hugging Face now charges for Docker Spaces, so `deploy/space` is kept only as a ready-made image for a future
host (for example an Oracle Always Free VM or Cloud Run).

## Where things live on the backend PC
- `~/pf-debate-runtime/run.cmd` starts the server and the tunnel, and restarts either if it exits. Logs go to `server.log` and `tunnel.log` in the same folder.
- `~/pf-debate-runtime/tunnel.token` is the tunnel's credential (keep it private). `cloudflared.exe` is the portable connector.
- `~/pf-debate-runtime/keys.cmd` (optional) holds the free-AI keys, e.g. `set CEREBRAS_API_KEY=...` and `set GROQ_API_KEY=...`.
- The Startup-folder entry `pf-debate.vbs` launches `run.cmd` hidden at logon.
- **The site is up only while this PC is on and awake.** Set it to never sleep while plugged in.

## Updating the backend
```
uv tool install --force --from C:/Users/sujay/pf-debate-mcp pf-debate-mcp    # frozen copy of the current code
taskkill /F /IM pf-debate-mcp.exe                                             # run.cmd restarts it within 10 s
```
Worker changes: `cd deploy/worker && npx wrangler deploy`. Pushing a tag also redeploys it, if the `CLOUDFLARE_API_TOKEN` secret is set.

## Moving the backend (e.g. to Oracle Always Free)
1. On the new host, run `pf-debate-mcp serve-http --public-url https://debate.peshcompsci.org --allowed-host debate.peshcompsci.org --allowed-host <its-hostname>`. `deploy/space/Dockerfile` also works.
2. Either run `cloudflared tunnel run --token-file tunnel.token` there, so no Worker change is needed; or delete the `[[vpc_services]]` block in wrangler.toml, set `BACKEND_URL`, and run `npx wrangler deploy`.
3. Remove the Startup entry on this PC.

## Routine operations
| Task | How |
|---|---|
| Deploy | Bump the versions in pyproject.toml, manifest.json and .claude-plugin/plugin.json. Push a tag `vX.Y.Z` (this runs tests, the Worker deploy if a token is set, and a smoke test). Then update the backend (above). |
| Roll back | Worker: `npx wrangler rollback` in deploy/worker. Backend: `uv tool install --force "pf-debate-mcp @ git+https://github.com/SujayGG/pf-debate-mcp@<older tag>"`, then kill pf-debate-mcp.exe. |
| Pause tool traffic | Set `KILL_SWITCH = "on"` in deploy/worker/wrangler.toml and run `npx wrangler deploy`. The landing page stays up. |

| New library version | Run `scripts/publish_library.py --version N+1 --upload`. Then run `pf-debate-mcp build-library` on the backend PC and restart the server. Local users update with `build_library`. |
| Rotate tokens | Create a new HF/Cloudflare token, update the repo secret, and revoke the old one. |
| Check usage | Open `https://debate.peshcompsci.org/stats` (counts only; no queries or content are ever logged). |

## When the nightly check opens an issue
1. Open `https://debate.peshcompsci.org/health`.
   - **"Waking up"**: the backend PC is off, asleep, or offline. Wake it. `run.cmd` starts at logon.
   - **Tunnel down**: check `tunnel.log` for "Registered tunnel connection" lines.
   - **Server down**: check `server.log`.
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
