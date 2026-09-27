import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const html = readFileSync(new URL("../hub.html", import.meta.url), "utf8");

test("hub page scripts parse (a syntax error blanks the whole site)", () => {
  const classic = [...html.matchAll(/<script(?![^>]*type="module")[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  assert.ok(classic.length >= 1);
  for (const s of classic) new Function(s); // throws SyntaxError on a broken script
});

test("break size comes from the first elim round's name", () => {
  const src = html.match(/function breakFromElims[\s\S]*?\r?\n}\r?\n/)[0];
  const breakFromElims = new Function(`${src}return breakFromElims;`)();
  const size = (label) => breakFromElims({ rounds: [{ prelim: true, label: "Round 1" }, { prelim: false, label }] });
  assert.deepEqual(["PF Q", "PF S", "Octafinals", "Doubles", "LD Quarters Partial", "Finals"].map(size), [8, 4, 16, 32, null, 2]);
});
