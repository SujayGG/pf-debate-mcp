// Keeps the hub polite to Tabroom and alive through Tabroom outages.
// - Cache API (per data center, free): every Tabroom-derived value lives `ttl` seconds, so however many phones watch
//   an entry, Tabroom sees about one request per key per window.
// - A failed fetch is remembered for 20 s, so an outage isn't hammered by retries.
// - KV (free tier: 1,000 writes/day) keeps the last good copy of `persist` keys, written only when the data changed,
//   so the hub can show "Tabroom is down; showing data from 2:41 PM".
import { TabroomDown } from "./tabroom.js";

const DOWN_TTL = 20;
const MAX_KV_WRITES = 900; // per isolate per day; ponytail: approximate cap, a KV counter would itself cost writes
let kvDay = "";
let kvWrites = 0;

const cacheReq = (key) => new Request(`https://hub.cache/${encodeURIComponent(key)}`);
const stored = (body, ttl) => new Response(JSON.stringify(body), {
  headers: { "content-type": "application/json", "cache-control": `max-age=${ttl}` } });

async function lastGood(kv, key, err) {
  const last = kv ? await kv.get(`h:${key}`, "json") : null;
  if (last) return { ...last, stale: true };
  throw err;
}

async function saveIfChanged(kv, key, body, now) {
  const day = new Date(now).toISOString().slice(0, 10);
  if (day !== kvDay) [kvDay, kvWrites] = [day, 0];
  if (kvWrites >= MAX_KV_WRITES) return;
  const prev = await kv.get(`h:${key}`, "json");
  if (prev && JSON.stringify(prev.data) === JSON.stringify(body.data)) return;
  kvWrites++;
  await kv.put(`h:${key}`, JSON.stringify(body), { expirationTtl: 60 * 60 * 24 * 14 });
}

/** {data, asOf, stale}. Throws TabroomDown only when Tabroom is down and there is no saved copy. */
export async function cached({ cache, kv, ctx, key, ttl, persist = false, fetcher, now = Date.now }) {
  const req = cacheReq(key);
  const hit = await cache.match(req);
  if (hit) {
    const body = await hit.json();
    return body.down ? lastGood(persist && kv, key, new TabroomDown("Tabroom is down")) : body;
  }
  try {
    const body = { data: await fetcher(), asOf: now(), stale: false };
    ctx.waitUntil(cache.put(req, stored(body, ttl)));
    if (persist && kv) ctx.waitUntil(saveIfChanged(kv, key, body, now()));
    return body;
  } catch (e) {
    if (!(e instanceof TabroomDown)) throw e;
    ctx.waitUntil(cache.put(req, stored({ down: true }, DOWN_TTL)));
    return lastGood(persist && kv, key, e);
  }
}
