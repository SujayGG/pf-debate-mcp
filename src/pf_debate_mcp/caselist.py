"""OpenCaselist client (api.opencaselist.com) using the user's own Tabroom login.

Only the session cookie is saved (~/.pf-debate/token); the password is never stored.
The API rate-limits searches (4/min) and downloads (10/min), so errors pass through.
"""

import os
import re

import httpx

from .store import HOME

API = "https://api.opencaselist.com/v1"
TOKEN = HOME / "token"


class CaselistError(RuntimeError):
    pass


def login(username: str, password: str) -> None:
    try:
        r = httpx.post(f"{API}/login", json={"username": username, "password": password, "remember": True},
                       timeout=30)
    except httpx.TransportError as e:
        raise CaselistError(f"Network problem reaching OpenCaselist ({type(e).__name__}).") from None
    token = r.cookies.get("caselist_token")
    if not token and r.is_success:
        try:
            token = r.json().get("token")  # the API now returns 201 with the token in the body
        except ValueError:
            token = None
    if not token:
        raise CaselistError(f"Login failed ({r.status_code}). Check your Tabroom email and password.")
    HOME.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(token)
    try:
        TOKEN.chmod(0o600)
    except OSError:
        pass


def _token() -> str:
    if TOKEN.exists():
        return TOKEN.read_text().strip()
    user, pw = os.environ.get("TABROOM_USERNAME"), os.environ.get("TABROOM_PASSWORD")
    if user and pw:
        login(user, pw)
        return TOKEN.read_text().strip()
    raise CaselistError("Not logged in to OpenCaselist. Run once in a terminal: uvx pf-debate-mcp login "
                        "(uses your Tabroom account), or set TABROOM_USERNAME/TABROOM_PASSWORD.")


def _get(path: str, **params) -> httpx.Response:
    try:
        r = httpx.get(f"{API}{path}", params=params, cookies={"caselist_token": _token()}, timeout=60)
    except httpx.TransportError as e:
        raise CaselistError(f"Network problem reaching OpenCaselist ({type(e).__name__}). Try again.") from None
    if r.status_code == 401:
        TOKEN.unlink(missing_ok=True)
        raise CaselistError("OpenCaselist session expired. Run: uvx pf-debate-mcp login")
    if r.status_code >= 400:
        raise CaselistError(f"OpenCaselist {path} -> {r.status_code}: {r.text[:200]}")
    return r


def current_pf() -> str:
    """Slug of the newest high-school PF caselist (e.g. 'hspf26')."""
    lists = [c for c in _get("/caselists").json() if c.get("event") == "pf"]
    hs = [c for c in lists if c.get("level", "hs") == "hs"] or lists
    if not hs:
        raise CaselistError("No PF caselist found.")
    return max(hs, key=lambda c: c.get("year") or 0)["name"]


def search(query: str, caselist: str | None = None) -> list[dict]:
    q = re.sub(r"[|~^;?!&%$*+=]", " ", query).strip()  # characters the API rejects
    hits = _get("/search", q=q, shard=caselist or current_pf()).json()
    keep = ("type", "caselist", "school", "school_display_name", "team", "team_display_name",
            "title", "path", "download_path", "snippet")
    return [{k: h[k] for k in keep if h.get(k)} for h in hits[:40]]


def _match(items: list[dict], wanted: str) -> dict:
    w = wanted.lower().replace(" ", "")
    for it in items:
        names = (it.get("name") or "", it.get("display_name") or "", it.get("displayName") or "")
        if any(w == n.lower().replace(" ", "") for n in names):
            return it
    for it in items:
        if any(w in (n or "").lower().replace(" ", "") for n in (it.get("name"), it.get("display_name"))):
            return it
    raise CaselistError(f"'{wanted}' not found. Options: " +
                        ", ".join((i.get("display_name") or i.get("name") or "") for i in items[:60]))


def team(school: str, team_name: str, caselist: str | None = None) -> dict:
    cl = caselist or current_pf()
    s = _match(_get(f"/caselists/{cl}/schools").json(), school)["name"]
    t = _match(_get(f"/caselists/{cl}/schools/{s}/teams").json(), team_name)["name"]
    base = f"/caselists/{cl}/schools/{s}/teams/{t}"
    rounds = [{k: r.get(k) for k in ("tournament", "side", "round", "opponent", "judge", "report", "opensource")
               if r.get(k)} for r in _get(f"{base}/rounds").json()]
    cites = [{k: c.get(k) for k in ("side", "tournament", "round", "title", "cites") if c.get(k)}
             for c in _get(f"{base}/cites").json()]
    return {"caselist": cl, "school": s, "team": t, "rounds": rounds, "cites": cites}


def parse_entries(text: str) -> list[dict]:
    """Tabroom field CSV (Institution,Location,Entry,Code,...) or lines like "Plano West, Park & Jiang"
    -> [{"school", "entry", "lasts": [last names]}]."""
    import csv
    import io

    rows = list(csv.reader(io.StringIO(text.strip().lstrip("﻿"))))
    if rows and rows[0] and rows[0][0].strip().lower() == "institution":
        head = [h.strip().lower() for h in rows[0]]
        rows = [[r[head.index("institution")], r[head.index("entry")]] for r in rows[1:] if len(r) >= len(head) - 1]
    out = []
    for r in rows:
        if len(r) < 2 or not r[0].strip():
            continue
        entry = r[1].strip()
        out.append({"school": r[0].strip(), "entry": entry,
                    "lasts": [p.strip() for p in re.split(r"\s*(?:&|/| and )\s*", entry) if p.strip()]})
    return out


def _same(a: str, b: str) -> bool:
    return re.sub(r"[^a-z]", "", a.lower()) == re.sub(r"[^a-z]", "", b.lower())


def _find_team(teams: list[dict], lasts: list[str]) -> dict | None:
    """A caselist team whose debaters' last names match, else whose code is the usual two-letter pairs (LiZh)."""
    want = sorted(re.sub(r"[^a-z]", "", n.lower()) for n in lasts)
    for t in teams:
        got = sorted(re.sub(r"[^a-z]", "", (t.get(k) or "").lower()) for k in ("debater1_last", "debater2_last"))
        if all(got) and got == want:
            return t
    codes = {"".join(n[:2].title() for n in lasts), "".join(n[:2].title() for n in reversed(lasts))}
    return next((t for t in teams if any(_same(t.get("name") or "", c) for c in codes)), None)


def scout_entries(text: str, caselist: str | None = None) -> list[dict]:
    """Match a tournament's entries to their caselist pages: what each team has disclosed."""
    cl = caselist or current_pf()
    schools = _get(f"/caselists/{cl}/schools").json()
    team_cache: dict[str, list] = {}
    out = []
    for e in parse_entries(text):
        row = {"school": e["school"], "entry": e["entry"]}
        s = next((s for s in schools if any(_same(s.get(k) or "", e["school"]) for k in ("display_name", "name"))),
                 None)
        if not s:
            out.append(row | {"status": "school not on the caselist"})
            continue
        if s["name"] not in team_cache:
            team_cache[s["name"]] = _get(f"/caselists/{cl}/schools/{s['name']}/teams").json()
        t = _find_team(team_cache[s["name"]], e["lasts"])
        if not t:
            out.append(row | {"status": "team not on the caselist", "caselist_school": s["name"]})
            continue
        base = f"/caselists/{cl}/schools/{s['name']}/teams/{t['name']}"
        rounds = _get(f"{base}/rounds").json()
        cites = _get(f"{base}/cites").json()
        docs = [{k: r.get(k) for k in ("side", "tournament", "round", "opensource") if r.get(k)}
                for r in rounds if r.get("opensource")]
        out.append(row | {"status": "disclosed" if rounds or cites else "page exists, nothing disclosed",
                          "caselist_school": s["name"], "caselist_team": t["name"], "rounds": len(rounds),
                          "open_source_docs": docs[-4:],
                          "cite_titles": [{"side": c.get("side"), "title": c.get("title")} for c in cites][-6:]})
    return out


def download(path: str) -> bytes:
    return _get("/download", path=path).content
