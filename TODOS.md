# TODOS

## Deferred from /plan-ceo-review (2026-09-24)

- **Verified-card receipts.** On `cut_card`, save the page to the Internet Archive (Wayback "Save Page" API, free) asynchronously and add the archive URL and a source-text hash to the cite. It must never block the cut. Why: articles change or get paywalled mid-season, and a snapshot keeps the card provable.
- **Auto-cut Chrome extension (design locked).**
  - On any page, the user types a claim.
  - If Chrome's built-in AI (Prompt API, Gemini Nano; Chromebook Plus or a desktop with 22 GB free) is available, cut on-device.
  - Otherwise, open the user's Claude/ChatGPT/Gemini with a prefilled prompt that uses the debate.peshcompsci.org connector.
  - The verbatim check always runs server-side.
  - Depends on: the hosted server (Release A).
- **Current-season caselist evidence.** Email the OpenCaselist maintainer about automated weekly-archive pulls before building ingestion (their ToS asks for coordination).

## From review (2026-09-24)

- **P1: Verify who can reach the connector before the hosted launch.**
  - Check Gemini teen and Workspace for Education support for custom MCP connectors, ChatGPT's teen policy, and whether school filters block claude.ai, gemini or chatgpt.
  - Why: the connector-first plan was kept, and Claude requires 18+.
  - Output: which setup guide to lead with on the landing page. Effort S.
- **P3: Free OAuth sign-in (GitHub/Google) for per-user quotas.** Trigger: /stats shows global budgets tripping from abuse. Effort M.
