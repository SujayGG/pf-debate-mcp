import assert from "node:assert/strict";
import { test } from "node:test";
import { cached } from "../hub/cache.js";
import { TabroomDown } from "../hub/tabroom.js";

function fakes() {
  const store = new Map();
  const cache = {
    async match(req) { const r = store.get(req.url); return r ? r.clone() : undefined; },
    async put(req, res) { store.set(req.url, res); },
    store,
  };
  const kvData = new Map();
  let writes = 0;
  const kv = {
    async get(k, type) { const v = kvData.get(k); return v && type === "json" ? JSON.parse(v) : v ?? null; },
    async put(k, v) { writes++; kvData.set(k, v); },
    get writes() { return writes; },
  };
  const pending = [];
  const ctx = { waitUntil: (p) => pending.push(p) };
  return { cache, kv, ctx, flush: () => Promise.all(pending.splice(0)) };
}

test("miss fetches and stores; hit skips Tabroom", async () => {
  const f = fakes();
  let calls = 0;
  const fetcher = async () => { calls++; return { round: 3 }; };
  const a = await cached({ ...f, key: "k", ttl: 60, fetcher, now: () => 1000 });
  await f.flush();
  const b = await cached({ ...f, key: "k", ttl: 60, fetcher });
  assert.equal(calls, 1);
  assert.deepEqual(a, { data: { round: 3 }, asOf: 1000, stale: false });
  assert.deepEqual(b, a);
});

test("Tabroom down: last good copy, marked stale; outage remembered", async () => {
  const f = fakes();
  await cached({ ...f, key: "e", ttl: 60, persist: true, fetcher: async () => ({ r: 1 }), now: () => 5 });
  await f.flush();
  f.cache.store.clear(); // TTL expired
  let calls = 0;
  const down = async () => { calls++; throw new TabroomDown("503"); };
  const s = await cached({ ...f, key: "e", ttl: 60, persist: true, fetcher: down });
  await f.flush();
  assert.deepEqual(s, { data: { r: 1 }, asOf: 5, stale: true });
  const s2 = await cached({ ...f, key: "e", ttl: 60, persist: true, fetcher: down });
  assert.equal(calls, 1); // the 20 s outage marker stopped the second call
  assert.equal(s2.stale, true);
});

test("Tabroom down and nothing saved: throws TabroomDown", async () => {
  const f = fakes();
  await assert.rejects(cached({ ...f, key: "x", ttl: 60, persist: true,
    fetcher: async () => { throw new TabroomDown("503"); } }), TabroomDown);
});

test("KV written only when the data changed; other errors propagate", async () => {
  const f = fakes();
  for (const v of [1, 1, 2]) {
    f.cache.store.clear();
    await cached({ ...f, key: "c", ttl: 60, persist: true, fetcher: async () => ({ v }) });
    await f.flush();
  }
  assert.equal(f.kv.writes, 2);
  await assert.rejects(cached({ ...f, key: "y", ttl: 60, fetcher: async () => { throw new TypeError("bug"); } }),
    TypeError);
});
