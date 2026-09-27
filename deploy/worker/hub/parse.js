// Parsers for Tabroom pages that need a login (entry record, judge page). They run in the viewer's browser on HTML
// the hub helper extension fetched with the viewer's own Tabroom session; this data never reaches our server.
// Served to browsers as-is (Text rule in wrangler.toml). Layouts verified on real pages from 2026-09-27.

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", mdash: "—", ndash: "–", rsquo: "’" };
// ponytail: duplicate of tabroom.js text(); the Worker imports that file as a module and this one as text
export function text(s) {
  return String(s).replace(/<[^>]+>/g, " ")
    .replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (m, e) => e[0] === "#"
      ? String.fromCodePoint(e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : Number(e.slice(1)))
      : ENTITIES[e.toLowerCase()] ?? m)
    .replace(/\s+/g, " ").trim();
}

const cellsOf = (row) => [...row.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => m[1]);
const blocks = (cell) => [...cell.matchAll(/<div class='judgeheight[^']*'>([\s\S]*?)<\/div>/g)].map((m) => m[1]);
const SIDE = { aff: "Pro", pro: "Pro", neg: "Con", con: "Con" };

/** Login-only entry record -> [{label, side, opponent:{id, code}, judges:[name], result, ballots, speaks}] */
export function parseEntryRecord(html) {
  const start = html.indexOf("Round Results");
  const table = html.slice(start).match(/<table[^>]*>([\s\S]*?)<\/table>/);
  if (start < 0 || !table) return null;
  const rounds = [];
  for (const row of table[1].matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const c = cellsOf(row[1]);
    if (c.length < 5) continue;
    const opp = c[2].match(/entry_id=(\d+)[^>]*>([\s\S]*?)<\/a>/);
    const votes = blocks(c[4]).map(text).filter((v) => v === "W" || v === "L");
    const w = votes.filter((v) => v === "W").length;
    const speaks = [...(c[5] || "").matchAll(/<span class="threefifths[^"]*">([\s\S]*?)<\/span>\s*<span[^>]*>([\s\S]*?)<\/span>\s*<span[^>]*>([\s\S]*?)<\/span>/g)]
      .map((m) => ({ name: text(m[1]), rank: Number(text(m[2])) || null, points: Number(text(m[3])) || null }));
    const sideWord = text(c[1]).toLowerCase().split(" ")[0];
    const bye = /bye/i.test(text(c[2]));
    rounds.push({
      label: text(c[0]), side: SIDE[sideWord] || null, bye,
      opponent: opp ? { id: Number(opp[1]), code: text(opp[2]).replace(/^vs\.?\s+/i, "") } : null,
      judges: blocks(c[3]).map(text).filter(Boolean),
      result: votes.length ? (w * 2 > votes.length ? "W" : "L") : bye ? "W" : null,
      ballots: votes.length > 1 ? `${w}-${votes.length - w}` : null, speaks,
    });
  }
  return rounds;
}

/** Login-only judge page -> {name, school, paradigm (text or null), decisions (this tournament), record (all)} */
export function parseJudgePage(html) {
  const name = html.match(/<h3[^>]*>([\s\S]*?)<\/h3>/);
  const school = html.match(/<h6[^>]*>([\s\S]*?)<\/h6>/);
  const paraStart = html.search(/class\s*=\s*"[^"]*\bparadigm\b[^"]*"/i);
  const paradigm = paraStart >= 0 ? text(html.slice(paraStart).match(/>([\s\S]*?)<\/div>/)?.[1] || "") || null : null;
  const recTable = html.match(/<table id="judgerecord">([\s\S]*?)<\/table>/);
  const record = [];
  for (const row of (recTable?.[1] || "").matchAll(/<tr>([\s\S]*?)<\/tr>/g)) {
    const c = cellsOf(row[1]);
    if (c.length < 8) continue;
    record.push({ tourn: text(c[0]), level: text(c[1]), date: text(c[2].replace(/<span class="hidden">[\s\S]*?<\/span>/, "")),
                  event: text(c[3]), round: text(c[4].replace(/<span class="hidden">[\s\S]*?<\/span>/, "")),
                  aff: text(c[5]), neg: text(c[6]), vote: text(c[7]) });
  }
  return { name: name ? text(name[1]) : null, school: school ? text(school[1]) : null, paradigm, record };
}

/** Voting summary for a judge card: rounds judged in the last year, and their Pro/Con split in PF. */
export function judgeSummary(record, now = Date.now()) {
  const year = record.filter((r) => now - new Date(r.date).getTime() < 365 * 86400000);
  const pf = year.filter((r) => /PF/i.test(r.event) && /^(aff|neg|pro|con)$/i.test(r.vote));
  const pro = pf.filter((r) => /^(aff|pro)$/i.test(r.vote)).length;
  return { rounds: year.length, pfDecisions: pf.length, pro, con: pf.length - pro,
           tournaments: new Set(year.map((r) => r.tourn)).size };
}
