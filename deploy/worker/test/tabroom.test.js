import assert from "node:assert/strict";
import { test } from "node:test";
import { TabroomDown, entryView, eventsOf, mapField, mapSchedule, parseTournId, tabroomGet } from "../hub/tabroom.js";

const SCHEDULE = mapSchedule([
  { id: 11, name: 1, label: "", type: "prelim", published: 1, startTime: "2026-09-26T13:00:00Z",
    Event: { id: 5, abbr: "VPF", name: "Varsity Public Forum", type: "debate" } },
  { id: 12, name: 2, label: "", type: "prelim", published: 1, startTime: "2026-09-26T15:00:00Z",
    Event: { id: 5, abbr: "VPF", name: "Varsity Public Forum", type: "debate" } },
  { id: 13, name: 3, label: "", type: "highlow", published: 1, startTime: "2026-09-26T17:00:00Z",
    Event: { id: 5, abbr: "VPF", name: "Varsity Public Forum", type: "debate" } },
  { id: 14, name: 4, label: "PF Semis", type: "elim", published: 0, startTime: "2026-09-26T21:00:00Z",
    Event: { id: 5, abbr: "VPF", name: "Varsity Public Forum", type: "debate" } },
  { id: 20, name: 1, label: "", type: "prelim", published: 1, startTime: "2026-09-26T13:00:00Z",
    Event: { id: 6, abbr: "VLD", name: "Varsity LD", type: "debate" } },
]);

const FIELD = mapField({ id: 5, name: "Varsity Public Forum", Entries: [
  { id: 100, name: "Park & Jiang", code: "Plano West Park & Jiang", active: 1, waitlist: 0,
    School: { name: "Plano West" }, Students: [{ firstName: "Ethan", lastName: "Park" }] },
  { id: 200, name: "Li & Zhang", code: "Jasper Li & Zhang", active: 1, waitlist: 0, School: { name: "Jasper" } },
  { id: 300, name: "Do & Maldonado", code: "Wylie Do & Maldonado", active: 1, waitlist: 0, School: { name: "Wylie" } },
  { id: 999, name: "Dropped", code: "X", active: 0, waitlist: 0, School: { name: "X" } },
] }, "VPF");

const sec = (a, b, judges, extra = {}) => ({ Room: { name: "B204" }, ...extra,
  Entries: { 1: a, 2: b }, Judges: judges });
const SCHEMATICS = {
  1: { label: "Round 1", Sections: { 1: sec({ id: 100, code: "PW PJ" }, { id: 200, code: "Jas LZ" },
    { 7: { first: "Pat", last: "Lee", paradigm: 555, chair: 1 } }) } },
  2: { label: "Round 2", Sections: { 2: { bye: 1, Entries: { 1: { id: 300, code: "Wy DM" } } },
    3: sec({ id: 200, code: "Jas LZ" }, { id: 100, code: "PW PJ" }, { 8: { first: "Sam", last: "Ng" } }) } },
  3: { label: "Round 3", Sections: {
    4: sec({ id: 100, code: "PW PJ", record: "1-1", wins: 1 }, { id: 300, code: "Wy DM", record: "2-0", wins: 2 },
      { 9: { first: "Ana", last: "Diaz", paradigm: 777 } }),
    5: { bye: 1, Entries: { 1: { id: 200, code: "Jas LZ", record: "1-1", wins: 1 } } } } },
};
const RECORDS = { id: 100, code: "PW PJ", Rounds: {
  1: { Results: { 7: { winloss: "W" } } },
  2: { Results: { 8: { winloss: "L" } } },
} };

test("field keeps active entries", () => {
  assert.deepEqual(FIELD.entries.map((e) => e.id), [100, 200, 300]);
  assert.equal(FIELD.entries[0].students[0], "Ethan Park");
});

test("entry view: rounds, current pairing, record, break inputs", () => {
  const v = entryView({ schedule: SCHEDULE, field: FIELD, schematics: SCHEMATICS, records: RECORDS,
                        entryId: 100, abbr: "VPF" });
  assert.equal(v.rounds.length, 4); // VLD round not mixed in
  assert.equal(v.rounds[0].side, "Pro");
  assert.equal(v.rounds[0].judges[0].personId, 555);
  assert.equal(v.rounds[0].result, "W");
  assert.equal(v.rounds[1].side, "Con");
  assert.equal(v.rounds[1].result, "L");
  assert.equal(v.current.name, 3);
  assert.equal(v.current.opponent.code, "Wy DM");
  assert.equal(v.current.opponent.record, "2-0");
  assert.equal(v.current.room, "B204");
  assert.deepEqual(v.record, { wins: 1, losses: 1, elims: [] });
  assert.equal(v.break.field, 3);
  assert.equal(v.break.prelims, 3);
  assert.equal(v.break.state.round, 3);
  assert.equal(v.break.state.wins.length, 3);
});

test("bye section and dropped/absent entry", () => {
  const v = entryView({ schedule: SCHEDULE, field: FIELD, schematics: SCHEMATICS, records: null,
                        entryId: 300, abbr: "VPF" });
  assert.equal(v.rounds[0].absent, true);
  assert.equal(v.rounds[1].bye, true);
  assert.equal(v.rounds[1].opponent, null);
});

test("anonymous event (no records) still shows pairings; nothing paired -> next round", () => {
  const v = entryView({ schedule: SCHEDULE, field: FIELD, schematics: { 1: SCHEMATICS[1] }, records: null,
                        entryId: 100, abbr: "VPF" });
  assert.equal(v.current.name, 1);
  const none = entryView({ schedule: SCHEDULE, field: FIELD, schematics: {}, records: null, entryId: 100,
                           abbr: "VPF" });
  assert.equal(none.current, null);
  assert.equal(none.next.name, 4);
});

test("events and tournament ids", () => {
  assert.deepEqual(eventsOf(SCHEDULE).map((e) => e.abbr), ["VPF", "VLD"]);
  assert.equal(parseTournId("https://www.tabroom.com/index/tourn/fields.mhtml?tourn_id=40176&event_id=1"), 40176);
  assert.equal(parseTournId(" 40176 "), 40176);
  assert.equal(parseTournId("prosper"), null);
});

const res = (status, body, type = "application/json") => new Response(body, { status, headers: { "content-type": type } });

test("maintenance page is an outage, 401/404 are 'not public'", async () => {
  await assert.rejects(tabroomGet("/x", async () => res(503, "<html>Site Maintenance</html>", "text/html")),
    TabroomDown);
  await assert.rejects(tabroomGet("/x", async () => res(200, "<html></html>", "text/html")), TabroomDown);
  await assert.rejects(tabroomGet("/x", async () => { throw new TypeError("fetch failed"); }), TabroomDown);
  assert.equal(await tabroomGet("/x", async () => res(401, "{}")), null);
  assert.deepEqual(await tabroomGet("/x", async () => res(200, '{"a":1}')), { a: 1 });
});
