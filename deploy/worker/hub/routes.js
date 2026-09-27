// /t/api/*: the hub's JSON API. Only public Tabroom endpoints; no credentials ever pass through here.
import { cached } from "./cache.js";
import { TabroomDown, entryView, eventsOf, mapField, mapSchedule, mapTourn, mapUpcoming, tabroomGet } from "./tabroom.js";

const MIN = 60;

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

export async function handleHub(request, env, ctx, { cache = caches.default, get = tabroomGet } = {}) {
  const { pathname } = new URL(request.url);
  if (!pathname.startsWith("/t/api/")) return null;
  const c = (key, ttl, fetcher, persist = false) => cached({ cache, kv: env.HUB_KV, ctx, key, ttl, persist, fetcher });
  const schedule = (id) => c(`sched:${id}`, 10 * MIN, async () =>
    mapSchedule(await get(`/rest/tourns/${id}/schedule`) || []));
  const field = (id, abbr) => c(`field:${id}:${abbr}`, 10 * MIN, async () =>
    mapField(await get(`/rest/tourns/${id}/events/${encodeURIComponent(abbr)}/field`), abbr), true);

  let m;
  try {
    if (pathname === "/t/api/upcoming") {
      return json(await c("upcoming", 60 * MIN, async () => mapUpcoming(await get("/pages/invite/upcoming")), true));
    }
    if ((m = pathname.match(/^\/t\/api\/tourn\/(\d{1,9})$/))) {
      const id = m[1];
      const body = await c(`tourn:${id}`, 10 * MIN, async () => {
        const t = mapTourn(await get(`/rest/tourns/${id}`));
        if (!t) return null;
        const s = (await schedule(id)).data;
        return { tourn: t, schedule: s, events: eventsOf(s) };
      }, true);
      return body.data ? json(body) : json({ error: "Tournament not found or not public." }, 404);
    }
    if ((m = pathname.match(/^\/t\/api\/tourn\/(\d{1,9})\/field\/([A-Za-z0-9]{1,12})$/))) {
      const body = await field(m[1], m[2]);
      return body.data ? json(body) : json({ error: "No public field for that event." }, 404);
    }
    if ((m = pathname.match(/^\/t\/api\/tourn\/(\d{1,9})\/event\/([A-Za-z0-9]{1,12})\/entry\/(\d{1,9})$/))) {
      const [, id, abbr, entryId] = m;
      return json(await c(`entry:${id}:${abbr}:${entryId}`, MIN, async () => {
        const sched = (await schedule(id)).data;
        const rounds = sched.filter((r) => r.event.abbr === abbr && r.published);
        const newest = rounds.slice(-2).map((r) => r.name);
        const [fld, records, ...schs] = await Promise.all([
          field(id, abbr).then((b) => b.data),
          c(`rec:${id}:${entryId}`, MIN, () => get(`/rest/tourns/${id}/entries/${entryId}/records`)).then((b) => b.data),
          ...rounds.map((r) => c(`sch:${id}:${abbr}:${r.name}`, newest.includes(r.name) ? MIN : 10 * MIN,
            () => get(`/pages/invite/${id}/${encodeURIComponent(abbr)}/${r.name}`)).then((b) => b.data)),
        ]);
        const schematics = Object.fromEntries(rounds.map((r, i) => [r.name, schs[i]]));
        return entryView({ schedule: sched, field: fld, schematics, records, entryId, abbr });
      }, true));
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
