// Tabroom's official public API (IndexCards, https://api.tabroom.com/v1) and mappers into the small shapes the
// hub page uses. Shapes follow the indexcards source (api/controllers/pages/invite/schematController.js and
// api/services/results/entryRecords.js). Mapping lives only here, so a Tabroom schema change breaks one file.

export const API = "https://api.tabroom.com/v1";
const UA = "pf-debate hub (+https://debate.peshcompsci.org/about)";
const PRELIMS = new Set(["prelim", "highlow", "highhigh", "snaked_prelim", "snakedPrelim"]);

export class TabroomDown extends Error {}

/** JSON from a public endpoint. null for "not there / not public" (404, 401); throws TabroomDown otherwise. */
export async function tabroomGet(path, fetchImpl = fetch) {
  let res;
  try {
    res = await fetchImpl(API + path, {
      headers: { accept: "application/json", "user-agent": UA },
      signal: AbortSignal.timeout(8000),
    });
  } catch (e) {
    throw new TabroomDown(`Tabroom unreachable (${e.name})`);
  }
  if (res.status === 401 || res.status === 404) return null;
  const type = res.headers.get("content-type") || "";
  if (!res.ok || !type.includes("json")) throw new TabroomDown(`Tabroom answered ${res.status}`);
  return res.json();
}

export function parseTournId(text) {
  const m = String(text || "").match(/tourn_id=(\d+)/) || String(text || "").match(/^\s*(\d{3,})\s*$/);
  return m ? Number(m[1]) : null;
}

export function mapTourn(t) {
  if (!t) return null;
  return { id: t.id, name: t.name, city: t.city, state: t.state, start: t.start, end: t.end, tz: t.tz,
           webname: t.webname };
}

export function mapUpcoming(list) {
  return (Array.isArray(list) ? list : [])
    .map((t) => ({ id: t.id ?? t.tourn_id ?? t.tournId, name: t.name, city: t.city, state: t.state,
                   dates: t.fullDates || t.dates, modes: (t.modes || "").trim(), events: t.events || "" }))
    .filter((t) => t.id && t.name);
}

export function mapSchedule(rounds) {
  return (Array.isArray(rounds) ? rounds : []).map((r) => ({
    id: r.id, name: Number(r.name), label: r.label || "", type: r.type, published: Number(r.published) > 0,
    start: r.startTime || r.Timeslot?.start || null,
    event: { id: r.Event?.id, abbr: r.Event?.abbr, name: r.Event?.name, type: r.Event?.type },
  })).sort((a, b) => a.name - b.name);
}

/** Events that have rounds, from the schedule. */
export function eventsOf(schedule) {
  const out = new Map();
  for (const r of schedule) if (r.event.abbr && !out.has(r.event.abbr)) out.set(r.event.abbr, r.event);
  return [...out.values()];
}

export function mapField(f, abbr) {
  if (!f) return null;
  const entries = (f.Entries || []).filter((e) => e.active !== 0 && !e.waitlist).map((e) => ({
    id: e.id, name: e.name, code: e.code, school: e.School?.name || "",
    students: (e.Students || []).map((s) => `${s.firstName} ${s.lastName}`.trim()),
  }));
  return { event: { id: f.id, name: f.name, abbr }, entries };
}

function sideLabels(event) {
  const pf = /PF|public forum/i.test(`${event?.abbr} ${event?.name}`);
  return pf ? { 1: "Pro", 2: "Con" } : { 1: "Aff", 2: "Neg" };
}

function findSection(schematic, entryId) {
  for (const sec of Object.values(schematic?.Sections || {})) {
    for (const [side, e] of Object.entries(sec.Entries || {})) {
      if (Number(e.id) === Number(entryId)) return { sec, side };
    }
  }
  return null;
}

/**
 * One entry's tournament: every round (pairing + result), the current round, record, and break-math inputs.
 * schedule: mapSchedule output. field: mapField output (or null). schematics: {roundName: raw schematic | null}.
 * records: raw entry records (or null when anonymous/unpublished).
 */
export function entryView({ schedule, field, schematics, records, entryId, abbr }) {
  const rounds = schedule.filter((r) => r.event.abbr === abbr);
  const event = rounds[0]?.event || field?.event || { abbr };
  const sides = sideLabels(event);
  const me = field?.entries.find((e) => Number(e.id) === Number(entryId));
  const out = [];
  let latestState = null;
  for (const r of rounds) {
    const sch = schematics[r.name];
    const row = { name: r.name, label: sch?.label || r.label || `Round ${r.name}`, type: r.type, start: r.start,
                  prelim: PRELIMS.has(r.type), published: r.published || !!sch };
    const hit = sch && findSection(sch, entryId);
    if (hit) {
      const { sec, side } = hit;
      const mine = sec.Entries[side];
      const oppSide = Object.keys(sec.Entries).find((k) => k !== side);
      const opp = oppSide ? sec.Entries[oppSide] : null;
      row.side = sides[side] || null;
      row.room = sec.Room?.name || null;
      row.roomUrl = sec.Room?.url || null;
      row.flight = sec.flight || null;
      row.bye = !!sec.bye || !opp;
      row.opponent = opp ? { id: opp.id, code: opp.code, record: opp.record ?? null } : null;
      row.judges = Object.values(sec.Judges || {}).map((j) => ({
        name: `${j.first || ""} ${j.last || ""}`.trim() || "(judge names hidden)", personId: j.paradigm || null,
        chair: !!j.chair }));
      row.recordBefore = mine.record ?? null;
      if (row.prelim && Object.values(sch.Sections).every((s) => Object.values(s.Entries || {})
        .every((e) => typeof e.wins === "number"))) {
        latestState = { round: r.name, wins: Object.values(sch.Sections).flatMap((s) =>
          Object.values(s.Entries || {}).map((e) => ({ id: e.id, wins: e.wins }))) };
      }
    } else if (sch) {
      row.absent = true; // published, but this entry isn't in it (bye without a section, or dropped)
    }
    const rec = records?.Rounds?.[r.name];
    if (rec) {
      const votes = Object.values(rec.Results || {}).map((x) => x.winloss).filter(Boolean);
      const w = votes.filter((v) => v === "W").length;
      const l = votes.length - w;
      if (rec.bye || rec.advanced) row.result = "W";
      else if (votes.length) row.result = w > l ? "W" : "L";
      if (votes.length > 1) row.ballots = `${w}-${l}`;
      if (rec.forfeit) row.forfeit = true;
      if (rec.bye) row.bye = true;
    }
    out.push(row);
  }
  const current = [...out].reverse().find((r) => (r.opponent || r.bye) && !r.result) || null;
  const next = current ? null : out.find((r) => !r.published) || null;
  const prelims = out.filter((r) => r.prelim);
  const wins = prelims.filter((r) => r.result === "W").length;
  const losses = prelims.filter((r) => r.result === "L").length;
  return {
    event, entry: { id: Number(entryId), name: me?.name || records?.name || null, code: me?.code || records?.code || null,
                    school: me?.school || null },
    rounds: out, current, next,
    record: { wins, losses, elims: out.filter((r) => !r.prelim && r.result).map((r) => `${r.label} ${r.result}`) },
    break: { field: field?.entries.length || null, prelims: prelims.length, done: wins + losses, myWins: wins,
             state: latestState },
  };
}
