import assert from "node:assert/strict";
import { test } from "node:test";
import { defaultBreak, simulate } from "../hub/breakmath.js";

test("same seed, same answer", () => {
  const a = simulate({ field: 32, prelims: 5, breakSize: 8, sims: 500, seed: 7 });
  const b = simulate({ field: 32, prelims: 5, breakSize: 8, sims: 500, seed: 7 });
  assert.deepEqual(a, b);
});

test("64 teams, 6 prelims, break 16: 5-1 safe, 4-2 on the bubble", () => {
  const r = simulate({ field: 64, prelims: 6, breakSize: 16, sims: 3000 });
  assert.equal(r.safe, 5);
  assert.ok(r.bubble.includes(4));
  assert.ok(r.byWins[3].p < 0.05);
});

test("more wins never lowers the chance to clear", () => {
  const r = simulate({ field: 24, prelims: 4, breakSize: 4, sims: 3000 });
  const ps = Object.keys(r.byWins).map(Number).sort((a, b) => a - b).map((k) => r.byWins[k].p);
  for (let i = 1; i < ps.length; i++) assert.ok(ps[i] >= ps[i - 1]);
});

test("odd field and break >= field", () => {
  const odd = simulate({ field: 23, prelims: 4, breakSize: 8, sims: 500 });
  const n = Object.values(odd.byWins).reduce((s, x) => s + x.n, 0);
  assert.equal(n, 23 * 500);
  const all = simulate({ field: 6, prelims: 3, breakSize: 8, sims: 200 });
  assert.ok(Object.values(all.byWins).every((x) => x.p === 1));
});

test("live state: my chance from the real current wins", () => {
  const wins = Array.from({ length: 16 }, (_, i) => (i < 4 ? 3 : i < 10 ? 2 : 1));
  const top = simulate({ field: 16, prelims: 4, breakSize: 4, done: 3, wins, me: 0, sims: 2000 });
  const bottom = simulate({ field: 16, prelims: 4, breakSize: 4, done: 3, wins, me: 15, sims: 2000 });
  assert.ok(top.myChance > 0.5 && bottom.myChance === 0);
});

test("record only: chance from my wins so far", () => {
  const r = simulate({ field: 32, prelims: 5, breakSize: 8, done: 3, myWins: 3, sims: 2000 });
  const r0 = simulate({ field: 32, prelims: 5, breakSize: 8, done: 3, myWins: 0, sims: 2000 });
  assert.ok(r.myChance > 0.8 && r0.myChance < 0.05);
});

test("default break", () => {
  assert.equal(defaultBreak(64), 16);
  assert.equal(defaultBreak(23), 4);
  assert.equal(defaultBreak(5), 2);
});
