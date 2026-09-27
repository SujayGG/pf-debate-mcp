// Builds a realistic mock of the hub API (from the Prosper Eagles field) for browser checks while Tabroom's API
// is unavailable. Run: node test/mockdata.mjs > mock.json. Uses the real mappers, so the shapes match production.
import { entryView, eventsOf, mapField, mapSchedule } from "../hub/tabroom.js";

const names = [["Richland", "Ravula & Bhavanam"], ["Plano West", "Park & Jiang"], ["Jasper", "Li & Zhang"],
  ["Wylie", "Do & Maldonado"], ["Plano East", "Tran & Troung"], ["BASIS Plano", "Rao & Oleksyuk"],
  ["THEO Christian", "Nelson & Tsang"], ["Plano West", "Wang & Xie"], ["Richland", "Javed & Nathani"],
  ["Plano East", "Gaddam & Galu"]];
const ev = { id: 382288, abbr: "VPF", name: "Varsity Public Forum", type: "debate" };
const raw = [1, 2, 3, 4].map((n) => ({ id: 900 + n, name: n, type: n === 3 ? "highlow" : "prelim", published: n <= 3 ? 1 : 0,
  startTime: `2026-09-26T${12 + 2 * n}:00:00.000Z`, Event: ev }))
  .concat([{ id: 910, name: 5, label: "PF Semis", type: "elim", published: 0, startTime: "2026-09-26T22:00:00.000Z", Event: ev },
           { id: 911, name: 6, label: "PF Finals", type: "final", published: 0, startTime: "2026-09-26T23:30:00.000Z", Event: ev }]);
const schedule = mapSchedule(raw);
const field = mapField({ id: 382288, name: "Varsity Public Forum", Entries: names.map(([school, name], i) => ({
  id: 7375444 + i, name, code: `${school} ${name}`, active: 1, waitlist: 0, School: { name: school },
  Students: name.split(" & ").map((l) => ({ firstName: "", lastName: l })) })) }, "VPF");
const ids = field.entries.map((e) => e.id);
const wins = Object.fromEntries(ids.map((id) => [id, 0]));
const schematics = {};
for (const r of [1, 2, 3]) {
  const order = r < 3 ? ids.slice().sort((a, b) => ((a * 7 + r * 13) % 11) - ((b * 7 + r * 13) % 11))
    : ids.slice().sort((a, b) => wins[b] - wins[a]);
  const Sections = {};
  for (let i = 0; i < order.length; i += 2) {
    const [a, b] = r % 2 ? [order[i], order[i + 1]] : [order[i + 1], order[i]];
    Sections[r * 100 + i] = { Room: { name: `C${100 + i}` }, Entries: {
      1: { id: a, code: field.entries.find((e) => e.id === a).code, record: `${wins[a]}-${r - 1 - wins[a]}`, wins: wins[a] },
      2: { id: b, code: field.entries.find((e) => e.id === b).code, record: `${wins[b]}-${r - 1 - wins[b]}`, wins: wins[b] } },
      Judges: { [r * 10 + i]: { first: "Judge", last: `R${r}-${i}`, paradigm: 18000 + r * 10 + i, chair: 1 } } };
    if (r < 3) wins[(a + b + r) % 2 ? a : b]++;
  }
  schematics[r] = { label: `Round ${r}`, Sections };
}
const me = 7375445; // Plano West Park & Jiang
const records = { id: me, Rounds: {} };
for (const r of [1, 2]) {
  const sec = Object.values(schematics[r].Sections).find((s) => Object.values(s.Entries).some((e) => e.id === me));
  const winner = Object.values(schematics[r + 1]?.Sections || {}).flatMap((s) => Object.values(s.Entries))
    .find((e) => e.id === me);
  const won = winner ? winner.wins > (r === 1 ? 0 : 0) && winner.wins >= r : false;
  records.Rounds[r] = { Results: { [Object.keys(sec.Judges)[0]]: { winloss: won ? "W" : "L" } } };
}
const wrap = (data) => ({ data, asOf: Date.now() - 95000, stale: false });
const view = entryView({ schedule, field, schematics, records, entryId: me, abbr: "VPF" });
const out = {
  "/t/api/upcoming": wrap([
    { id: 40176, name: "Prosper Eagles TFA Tournament", city: "Prosper", state: "TX", dates: "Sat, September 26, 2026", modes: "In Person", events: "VPF, VLD, VCX" },
    { id: 40555, name: "Grapevine Classic", city: "Grapevine", state: "TX", dates: "Sat, October 10, 2026", modes: "In Person", events: "PF" },
    { id: 40777, name: "Online Fall Invitational", city: "", state: "CA", dates: "Oct 17-18, 2026", modes: "Online", events: "PF, LD" }]),
  "/t/api/tourn/40176": wrap({ tourn: { id: 40176, name: "Prosper Eagles TFA Tournament", city: "Prosper", state: "TX",
    start: "2026-09-26T11:00:00.000Z", end: "2026-09-27T04:00:00.000Z", tz: "America/Chicago" }, schedule, events: eventsOf(schedule) }),
  "/t/api/tourn/40176/field/VPF": wrap(field),
  [`/t/api/tourn/40176/event/VPF/entry/${me}`]: wrap(view),
  [`/t/api/tourn/40176/event/VPF/entry/${me}?stale`]: { data: view, asOf: Date.now() - 600000, stale: true },
};
console.log(JSON.stringify(out));
