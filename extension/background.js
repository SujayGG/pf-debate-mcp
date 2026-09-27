// Calls Tabroom's and OpenCaselist's APIs with the user's own browser sessions. Answers only the hub's content
// script, validates every argument, and returns plain data; nothing goes to pf-debate's server.
const TABROOM = "https://api.tabroom.com/v1";
const CASELIST = "https://api.opencaselist.com/v1";
const HUB = "https://debate.peshcompsci.org";
const WEB = "https://www.tabroom.com";
// Classic Tabroom pages the hub may read with your session (records, judge pages, fields). Nothing else.
const PAGES = [
  /^\/index\/tourn\/postings\/entry_record\.mhtml\?(tourn_id=\d+&entry_id=\d+|entry_id=\d+&tourn_id=\d+)$/,
  /^\/index\/tourn\/postings\/judge\.mhtml\?(judge_id=\d+&tourn_id=\d+|tourn_id=\d+&judge_id=\d+)$/,
  /^\/index\/tourn\/fields\.mhtml\?tourn_id=\d+&event_id=\d+$/,
];

async function tabroomToken() {
  for (const url of ["https://www.tabroom.com", "https://api.tabroom.com"]) {
    const c = await chrome.cookies.get({ url, name: "TabroomToken" });
    if (c?.value) return c.value;
  }
  return null;
}

async function tabroom(path) {
  const token = await tabroomToken();
  if (!token) throw new Error("login");
  const r = await fetch(TABROOM + path, { headers: { accept: "application/json", authorization: `Bearer ${token}` },
                                          credentials: "include" });
  if (r.status === 401 || r.status === 403) throw new Error("login");
  if (!r.ok) throw new Error(`Tabroom answered ${r.status}`);
  return r.json();
}

let caselistSlug = null;
async function caselist(path) {
  const r = await fetch(CASELIST + path, { credentials: "include", headers: { accept: "application/json" } });
  if (r.status === 401) throw new Error("login");
  if (!r.ok) throw new Error(`OpenCaselist answered ${r.status}`);
  return r.json();
}

async function currentPf() {
  if (caselistSlug) return caselistSlug;
  const lists = (await caselist("/caselists")).filter((c) => c.event === "pf" && (c.level || "hs") === "hs");
  if (!lists.length) throw new Error("no PF caselist");
  caselistSlug = lists.reduce((a, b) => ((b.year || 0) > (a.year || 0) ? b : a)).name;
  return caselistSlug;
}

const OPS = {
  async page({ path }) {
    const r = await fetch(WEB + path, { credentials: "include", headers: { accept: "text/html" } });
    if (r.url.includes("/user/login")) throw new Error("login");
    if (!r.ok) throw new Error(`Tabroom answered ${r.status}`);
    const html = await r.text();
    if (html.length > 3_000_000) throw new Error("page too large");
    return html;
  },
  async paradigm({ personId }) { return tabroom(`/rest/paradigms/${personId}`); },
  async judgeRecord({ personId }) { return tabroom(`/rest/paradigms/${personId}/record`); },
  async caselist({ q }) {
    const clean = q.replace(/[|~^;?!&%$*+=]/g, " ").trim(); // characters the caselist search rejects
    return caselist(`/search?q=${encodeURIComponent(clean)}&shard=${await currentPf()}`);
  },
};

function valid(op, args) {
  if (!OPS[op] || typeof args !== "object" || !args) return false;
  if (op === "caselist") return typeof args.q === "string" && args.q.length > 0 && args.q.length <= 120;
  if (op === "page") return typeof args.path === "string" && PAGES.some((re) => re.test(args.path));
  return Number.isInteger(args.personId) && args.personId > 0;
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!sender.url?.startsWith(HUB + "/") || !valid(msg?.op, msg?.args)) {
    reply({ ok: false, error: "rejected" });
    return false;
  }
  OPS[msg.op](msg.args).then((data) => reply({ ok: true, data }),
                              (e) => reply({ ok: false, error: e.message || "failed" }));
  return true; // async reply
});
