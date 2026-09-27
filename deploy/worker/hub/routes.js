// /t/api/*: the hub's JSON API. Only public Tabroom data; no credentials ever pass through here.
// Source order: Tabroom's v4 API (full data) -> when it's down, the older API for listings and the classic public
// pairings pages for tournaments/rounds (no records there: those need a login). Views say which source they used.
import { cached } from "./cache.js";
import {
  TabroomDown, entryView, eventsOf, fieldFromRound, legacyGet, mapField, mapLegacyUpcoming, mapSchedule, mapTourn,
  mapUpcoming, parsePostings, parseRoundPage, tabroomGet, webGet, webSchedule,
} from "./tabroom.js";

const MIN = 60;

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

const orFallback = (primary, fallback) => primary().catch((e) => {
  if (e instanceof TabroomDown) return fallback();
  throw e;
});

export async function handleHub(request, env, ctx,
                                { cache = caches.default, get = tabroomGet, legacy = legacyGet, web = webGet } = {}) {
  const { pathname } = new URL(request.url);
  if (!pathname.startsWith("/t/api/")) return null;
  const c = (key, ttl, fetcher, persist = false) => cached({ cache, kv: env.HUB_KV, ctx, key, ttl, persist, fetcher });
  const data = async (p) => (await p).data;

  // v4 API pieces
  const schedule = (id) => data(c(`sched:${id}`, 10 * MIN, async () =>
    mapSchedule(await get(`/rest/tourns/${id}/schedule`) || [])));
  const apiField = async (id, abbr) => mapField(await get(`/rest/tourns/${id}/events/${encodeURIComponent(abbr)}/field`), abbr);

  // classic public pages
  const postings = (id) => data(c(`web:post:${id}`, 10 * MIN, async () => {
    const idx = await web(`/index/tourn/postings/index.mhtml?tourn_id=${id}`);
    const rid = (idx.redirect || "").match(/round_id=(\d+)/)?.[1];
    if (!rid) return idx.html ? parsePostings(idx.html) : null; // nothing posted yet, or not public
    const page = await web(`/index/tourn/postings/round.mhtml?tourn_id=${id}&round_id=${rid}`);
    return page.html ? parsePostings(page.html) : null;
  }));
  const roundPage = (id, roundId, ttl) => data(c(`web:round:${id}:${roundId}`, ttl, async () => {
    const p = await web(`/index/tourn/postings/round.mhtml?tourn_id=${id}&round_id=${roundId}`);
    return p.html ? parseRoundPage(p.html) : null;
  }));
  const webRounds = async (id, abbr) => {
    const post = await postings(id);
    return { post, rounds: post ? webSchedule(post).filter((r) => r.event.abbr === abbr) : [] };
  };
  const webField = async (id, abbr) => {
    const { rounds } = await webRounds(id, abbr);
    const first = rounds.find((r) => r.type === "prelim") || rounds[0];
    return first ? { ...fieldFromRound(await roundPage(id, first.id, 10 * MIN), abbr), source: "web" } : null;
  };

  let m;
  try {
    if (pathname === "/t/api/upcoming") {
      return json(await c("upcoming", 60 * MIN, () => orFallback(
        async () => mapUpcoming(await get("/pages/invite/upcoming")),
        async () => mapLegacyUpcoming(await legacy("/public/invite/upcoming"))), true));
    }
    if ((m = pathname.match(/^\/t\/api\/tourn\/(\d{1,9})$/))) {
      const id = m[1];
      const body = await c(`tourn:${id}`, 10 * MIN, () => orFallback(async () => {
        const t = mapTourn(await get(`/rest/tourns/${id}`));
        if (!t) return null;
        const s = await schedule(id);
        return { tourn: t, schedule: s, events: eventsOf(s), source: "api" };
      }, async () => {
        const post = await postings(id);
        if (!post) return null;
        const s = webSchedule(post);
        return { tourn: { id: Number(id), name: post.name, city: post.city, state: post.state, tz: null },
                 schedule: s, events: eventsOf(s), source: "web" };
      }), true);
      return body.data ? json(body) : json({ error: "Tournament not found or not public." }, 404);
    }
    if ((m = pathname.match(/^\/t\/api\/tourn\/(\d{1,9})\/field\/([A-Za-z0-9]{1,12})$/))) {
      const [, id, abbr] = m;
      const body = await c(`field:${id}:${abbr}`, 10 * MIN,
        () => orFallback(() => apiField(id, abbr), () => webField(id, abbr)), true);
      return body.data ? json(body) : json({ error: "No public field for that event." }, 404);
    }
    if ((m = pathname.match(/^\/t\/api\/tourn\/(\d{1,9})\/event\/([A-Za-z0-9]{1,12})\/entry\/(\d{1,9})$/))) {
      const [, id, abbr, entryId] = m;
      return json(await c(`entry:${id}:${abbr}:${entryId}`, MIN, () => orFallback(async () => {
        const sched = await schedule(id);
        const rounds = sched.filter((r) => r.event.abbr === abbr && r.published);
        const newest = rounds.slice(-2).map((r) => r.name);
        const [fld, records, ...schs] = await Promise.all([
          data(c(`field:${id}:${abbr}`, 10 * MIN, () => apiField(id, abbr), true)),
          data(c(`rec:${id}:${entryId}`, MIN, () => get(`/rest/tourns/${id}/entries/${entryId}/records`))),
          ...rounds.map((r) => data(c(`sch:${id}:${abbr}:${r.name}`, newest.includes(r.name) ? MIN : 10 * MIN,
            () => get(`/pages/invite/${id}/${encodeURIComponent(abbr)}/${r.name}`)))),
        ]);
        const schematics = Object.fromEntries(rounds.map((r, i) => [r.name, schs[i]]));
        return { ...entryView({ schedule: sched, field: fld, schematics, records, entryId, abbr }), source: "api" };
      }, async () => {
        const { rounds } = await webRounds(id, abbr);
        const newest = rounds.slice(-2).map((r) => r.id);
        const pages = await Promise.all(rounds.map((r) => roundPage(id, r.id, newest.includes(r.id) ? MIN : 10 * MIN)));
        const schematics = Object.fromEntries(rounds.map((r, i) => [r.name, pages[i]]));
        const first = rounds.findIndex((r) => r.type === "prelim");
        const fld = first >= 0 ? fieldFromRound(pages[first], abbr) : null;
        return { ...entryView({ schedule: rounds, field: fld, schematics, records: null, entryId, abbr }), source: "web" };
      }), true));
    }
    return json({ error: "Unknown hub endpoint." }, 404);
  } catch (e) {
    if (e instanceof TabroomDown) {
      return json({ error: "Tabroom is not answering right now and we have no saved copy yet. Retrying shortly.", down: true },
        503);
    }
    throw e;
  }
}
