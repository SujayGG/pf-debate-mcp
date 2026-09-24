from pf_debate_mcp.cards import runs_from_markup
from pf_debate_mcp.docx_io import export, parse

CARD = {
    "tag": "Moratorium kills US AI lead",
    "cite_short": "Smith 25",
    "cite_rest": "[Jane Smith; fellow at CSIS; \"Compute\" Foreign Affairs; 2025]",
    "runs": [("Compute is ", False, False), ("the binding constraint", True, True),
             (" on frontier AI, and ", True, False), ("China is catching up", True, True), (".", False, False)],
}


def test_round_trip(tmp_path):
    path = export("Aff Case", [{"pocket": "Aff"}, {"block": "C1: AI"}, {"card": CARD}, {"text": "Analytic."}],
                  tmp_path / "case.docx")
    cards = parse(path.read_bytes())
    assert len(cards) == 1
    c = cards[0]
    assert (c["pocket"], c["block"], c["tag"], c["cite_short"]) == ("Aff", "C1: AI", CARD["tag"], "Smith 25")
    assert c["cite_rest"] == CARD["cite_rest"]
    assert c["runs"] == CARD["runs"]


def test_dataset_markup():
    m = "<h4>Tag</h4><p><strong>X 12</strong> cite</p><p>Lastly, <u><mark>weak <strong>econ</strong></mark>. Other</u> text</p>"
    assert runs_from_markup(m) == [("Lastly, ", False, False), ("weak econ", True, True),
                                   (". Other", True, False), (" text", False, False)]
