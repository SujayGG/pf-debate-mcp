"""Tournament field -> caselist matching (no network: the API is faked)."""

from pf_debate_mcp import caselist as cl

CSV = """Institution,Location,Entry,Code,Record
Plano West,TX/US,Park & Jiang,Plano West Ethan Park & Calvin Jiang,
Jasper,TX/US,Li & Zhang,Jasper Andrew Li & Aidan Zhang,
Wylie,TX/US,Do & Maldonado,Wylie Dylan Do & Kevinn Maldonado,
Nowhere High,TX/US,A & B,x,
"""

API = {
    "/caselists/hspf26/schools": [{"name": "PlanoWest", "display_name": "Plano West"},
                                  {"name": "Jasper", "display_name": "Jasper"}, {"name": "Wylie"}],
    "/caselists/hspf26/schools/PlanoWest/teams": [{"name": "JiPa", "debater1_last": "Jiang", "debater2_last": "Park"}],
    "/caselists/hspf26/schools/Jasper/teams": [{"name": "LiZh"}],  # no debater names: code match
    "/caselists/hspf26/schools/Wylie/teams": [],
    "/caselists/hspf26/schools/PlanoWest/teams/JiPa/rounds": [{"side": "A", "tournament": "Grapevine",
                                                               "opensource": "hspf26/PW/JiPa-Aff.docx"}],
    "/caselists/hspf26/schools/PlanoWest/teams/JiPa/cites": [{"side": "A", "title": "Cyber"}],
    "/caselists/hspf26/schools/Jasper/teams/LiZh/rounds": [],
    "/caselists/hspf26/schools/Jasper/teams/LiZh/cites": [],
}


class _R:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


def test_scout_entries(monkeypatch):
    monkeypatch.setattr(cl, "_get", lambda path, **kw: _R(API[path]))
    got = {r["school"]: r for r in cl.scout_entries(CSV, "hspf26")}
    pw = got["Plano West"]
    assert pw["status"] == "disclosed" and pw["caselist_team"] == "JiPa"
    assert pw["open_source_docs"][0]["opensource"] == "hspf26/PW/JiPa-Aff.docx"
    assert got["Jasper"]["status"] == "page exists, nothing disclosed" and got["Jasper"]["caselist_team"] == "LiZh"
    assert got["Wylie"]["status"] == "team not on the caselist"
    assert got["Nowhere High"]["status"] == "school not on the caselist"


def test_plain_lines():
    assert cl.parse_entries("Richland, Javed & Nathani") == [
        {"school": "Richland", "entry": "Javed & Nathani", "lasts": ["Javed", "Nathani"]}]
