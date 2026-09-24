// debate.peshcompsci.org: the front door for the free pf-debate server.
//
//   student's AI app ──▶ this Worker ──▶ Hugging Face Space (BACKEND_URL) running `pf-debate-mcp serve-http`
//
// - "/" serves the landing page and "/app" the web app (bundled from landing.html and app.html).
// - "/api/*" is the web app's API (same health gate as /mcp).
// - "/mcp" is proxied only after a quick health check, so a sleeping Space turns into a clear
//   "waking up" message within ~8 s instead of a hang (the Space sleeps after 48 h without traffic).
// - A cron pings /health every 12 h so the Space rarely sleeps at all.
// - KILL_SWITCH="on" stops tool traffic instantly without touching the backend.
// - BACKEND_URL is config, so the backend can move to another free host without students re-adding the URL.
// CPU cost is tiny (network waits don't count toward the free plan's 10 ms CPU limit).

import LANDING from "./landing.html";
import APP from "./app.html";

const HEALTH_TTL_MS = 60_000;

// Reach the backend: through Workers VPC (a private Cloudflare Tunnel binding, no public origin) when the
// BACKEND binding exists, otherwise over the internet at BACKEND_URL. Switching hosts is config only.
function backendFetch(env, pathAndQuery, init) {
  if (env.BACKEND) return env.BACKEND.fetch(new Request("http://127.0.0.1:7860" + pathAndQuery, init));
  return fetch(new Request(new URL(pathAndQuery, env.BACKEND_URL), init));
}
let lastHealthy = 0; // per-isolate cache: skip the health probe when the backend answered recently

async function backendHealthy(env) {
  if (Date.now() - lastHealthy < HEALTH_TTL_MS) return true;
  try {
    const r = await backendFetch(env, "/health", { signal: AbortSignal.timeout(8000) });
    if (r.ok) lastHealthy = Date.now();
    return r.ok;
  } catch {
    return false;
  }
}

async function mcpError(request, message, status) {
  // Answer a JSON-RPC call with a JSON-RPC error so the AI can read and relay the message.
  let id = null;
  try {
    id = (await request.clone().json()).id ?? null;
  } catch {}
  if (request.method === "POST" && id !== null) {
    return Response.json({ jsonrpc: "2.0", id, error: { code: -32000, message } });
  }
  return new Response(message, { status, headers: { "Retry-After": "60" } });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const page = { "/": LANDING, "/index.html": LANDING, "/app": APP, "/app/": APP }[url.pathname];
    if (page) {
      return new Response(page, {
        headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" },
      });
    }
    if (url.pathname === "/mcp" || url.pathname.startsWith("/api/")) {
      if (env.KILL_SWITCH === "on") {
        return mcpError(request, "The free pf-debate server is paused for maintenance. Try again later, "
          + "or install it locally: github.com/SujayGG/pf-debate-mcp", 503);
      }
      if (!(await backendHealthy(env))) {
        ctx.waitUntil(backendFetch(env, "/health").catch(() => {})); // nudge it awake
        return mcpError(request, "The free pf-debate server is waking up (about 1 minute). "
          + "Please try again shortly.", 503);
      }
    }
    const proxied = ["/mcp", "/health", "/stats"].includes(url.pathname) ||
      url.pathname.startsWith("/files/") || url.pathname.startsWith("/api/");
    if (!proxied) {
      return new Response("Not found", { status: 404 });
    }
    const headers = new Headers(request.headers);
    // The web app's per-IP limits need the student's IP; connector traffic arrives from AI providers instead.
    headers.set("cf-connecting-ip", request.headers.get("cf-connecting-ip") || "");
    return backendFetch(env, url.pathname + url.search, {  // streams bodies both ways (SSE included)
      method: request.method, headers, body: request.body, redirect: "manual",
    });
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(backendFetch(env, "/health").catch(() => {}));
  },
};
