import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const html = readFileSync(new URL("../hub.html", import.meta.url), "utf8");

test("hub page scripts parse (a syntax error blanks the whole site)", () => {
  const classic = [...html.matchAll(/<script(?![^>]*type="module")[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  assert.ok(classic.length >= 1);
  for (const s of classic) new Function(s); // throws SyntaxError on a broken script
});
