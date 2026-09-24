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
    r = httpx.post(f"{API}/login", json={"username": username, "password": password, "remember": True},
                   timeout=30)
    if r.status_code != 200 or "caselist_token" not in r.cookies:
        raise CaselistError(f"Login failed ({r.status_code}): {r.text[:200]}")
    HOME.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(r.cookies["caselist_token"])
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
    r = httpx.get(f"{API}{path}", params=params, cookies={"caselist_token": _token()}, timeout=60)
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


def download(path: str) -> bytes:
    return _get("/download", path=path).content
