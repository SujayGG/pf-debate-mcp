import assert from "node:assert/strict";
import { test } from "node:test";
import { handleHub } from "../hub/routes.js";
import { TabroomDown } from "../hub/tabroom.js";

function deps(responses, { down = false } = {}) {
  const store = new Map();
  const cache = {
    async match(req) { const r = store.get(req.url); return r ? r.clone() : undefined; },
    async put(req, res) { store.set(req.url, res); },
  };
  const calls = [];
  const get = async (path) => {
    calls.push(path);
    if (down) throw new TabroomDown("503");
    if (!(path in responses)) return null;
    return structuredClone(responses[path]);
  };
  const ctx = { waitUntil() {} };
  return { opts: { cache, get }, ctx, calls };
}

const T = {
  "/rest/tourns/40176": { id: 40176, name: "Prosper Eagles TFA Tournament", city: "Prosper", state: "TX" },
  "/rest/tourns/40176/schedule": [
    { id: 1, name: 1, type: "prelim", published: 1, startTime: "2026-09-26T13:00:00Z",
      Event: { id: 5, abbr: "VPF", name: "Varsity Public Forum", type: "debate" } },
    { id: 2, name: 2, type: "prelim", published: 0, startTime: "2026-09-26T15:00:00Z",
      Event: { id: 5, abbr: "VPF", name: "Varsity Public Forum", type: "debate" } }],
  "/rest/tourns/40176/events/VPF/field": { id: 5, name: "Varsity Public Forum", Entries: [
    { id: 100, name: "Park & Jiang", code: "PW PJ", active: 1, School: { name: "Plano West" } },
    { id: 200, name: "Li & Zhang", code: "Jas LZ", active: 1, School: { name: "Jasper" } }] },
  "/pages/invite/40176/VPF/1": { label: "Round 1", Sections: { 9: { Room: { name: "A1" },
    Entries: { 1: { id: 100, code: "PW PJ" }, 2: { id: 200, code: "Jas LZ" } },
    Judges: { 3: { first: "Pat", last: "Lee", paradigm: 555 } } } } },
};

const req = (p) => new Request(`https://debate.peshcompsci.org${p}`);

test("entry endpoint composes schedule, field, pairings", async () => {
  const d = deps(T);
  const res = await handleHub(req("/t/api/tourn/40176/event/VPF/entry/100"), {}, d.ctx, d.opts);
  assert.equal(res.status, 200);
  const { data, stale } = await res.json();
  assert.equal(stale, false);
  assert.equal(data.current.opponent.code, "Jas LZ");
  assert.equal(data.current.judges[0].personId, 555);
  assert.equal(data.next, null);
  assert.ok(!d.calls.includes("/pages/invite/40176/VPF/2")); // unpublished rounds aren't requested
});

test("tournament, field, bad input, not found", async () => {
  const d = deps(T);
  const t = await (await handleHub(req("/t/api/tourn/40176"), {}, d.ctx, d.opts)).json();
  assert.equal(t.data.tourn.name, "Prosper Eagles TFA Tournament");
  assert.deepEqual(t.data.events.map((e) => e.abbr), ["VPF"]);
  const f = await (await handleHub(req("/t/api/tourn/40176/field/VPF"), {}, d.ctx, d.opts)).json();
  assert.equal(f.data.entries.length, 2);
  assert.equal((await handleHub(req("/t/api/tourn/1"), {}, d.ctx, d.opts)).status, 404);
  assert.equal((await handleHub(req("/t/api/tourn/40176/field/V%20PF"), {}, d.ctx, d.opts)).status, 404);
  assert.equal(await handleHub(req("/cards"), {}, d.ctx, d.opts), null);
});

test("Tabroom down with nothing saved: 503 with a readable message", async () => {
  const d = deps(T, { down: true });
  const res = await handleHub(req("/t/api/tourn/40176/event/VPF/entry/100"), {}, d.ctx, d.opts);
  assert.equal(res.status, 503);
  assert.equal((await res.json()).down, true);
});
