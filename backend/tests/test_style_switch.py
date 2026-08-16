"""Switching the citation style must restyle the whole export, and the
picker must be able to say what that switch does before it happens."""
import pytest
from fastapi.testclient import TestClient

from app import store
from app.cslproc.render import list_styles, style_samples
from app.export.latex import build_latex
from app.main import app


@pytest.fixture
def client(simple_doc, monkeypatch, tmp_path):
    monkeypatch.setattr(store.settings, "data_dir", tmp_path)
    store.save_paper(simple_doc)
    return TestClient(app)


def test_every_style_ships_notes(client):
    styles = client.get("/api/styles").json()
    assert {s["id"] for s in styles} == {
        "apa", "chicago-author-date", "harvard-cite-them-right", "ieee", "nature"}
    for s in styles:
        assert s["family"] in {"author–date", "numeric"}
        assert s["in_text"] and s["bibliography"] and s["changes"]


def test_setting_style_restyles_the_rendered_paper(client, simple_doc):
    pid = simple_doc.id
    before = client.get(f"/api/papers/{pid}/rendered").json()
    assert "[1]" in before["sections"][1]["html"]        # doc default: ieee

    assert client.post(f"/api/papers/{pid}/style", json={"style": "apa"}).status_code == 200

    # the stored paper, the reader view, and main.tex all move together
    assert client.get(f"/api/papers/{pid}").json()["csl_style"] == "apa"
    after = client.get(f"/api/papers/{pid}/rendered").json()
    assert "(Smith, 2020)" in after["sections"][1]["html"]
    assert "[1]" not in after["sections"][1]["html"]

    tex = client.get(f"/api/papers/{pid}/export/main.tex").text
    assert r"\citep{ref_1}" in tex and r"\usepackage[round]{natbib}" in tex
    assert "Smith, J.. (2020)" in tex


def test_numeric_export_drops_natbib(client, simple_doc):
    client.post(f"/api/papers/{simple_doc.id}/style", json={"style": "nature"})
    tex = client.get(f"/api/papers/{simple_doc.id}/export/main.tex").text
    assert r"\cite{ref_1}" in tex
    assert "natbib" not in tex


def test_style_query_overrides_the_stored_style(client, simple_doc):
    """The export screen sends the style explicitly, so a request must not
    silently fall back to whatever is on disk."""
    pid = simple_doc.id                                   # stored style: ieee
    rendered = client.get(f"/api/papers/{pid}/rendered?style=apa").json()
    assert rendered["style"] == "apa"
    assert "(Smith, 2020)" in rendered["sections"][1]["html"]
    assert store.load_paper(pid).csl_style == "ieee"      # a preview, not a write

    zip_ieee = client.get(f"/api/papers/{pid}/export.zip").content
    zip_apa = client.get(f"/api/papers/{pid}/export.zip?style=apa").content
    assert zip_ieee != zip_apa


def test_all_files_in_the_zip_follow_the_style(simple_doc):
    ieee = build_latex(simple_doc, "ieee")
    apa = build_latex(simple_doc, "apa")
    assert "[1]" in ieee["paper.md"] and "(Smith, 2020)" in apa["paper.md"]
    assert ieee["main.tex"] != apa["main.tex"]
    # references.bib is canonical data, not a rendering — it must NOT change
    assert ieee["references.bib"] == apa["references.bib"]


def test_style_samples_come_from_the_papers_own_references(client, simple_doc):
    samples = client.get(f"/api/papers/{simple_doc.id}/style-samples").json()
    assert set(samples) == {s["id"] for s in list_styles()}
    assert samples["apa"]["parenthetical"] == "(Smith, 2020)"
    assert samples["ieee"]["parenthetical"] == "[1]"
    assert samples["ieee"]["group"] == "[1], [2]"
    # author-year sorts the sample bibliography, numeric keeps citation order
    assert [b.split(",")[0] for b in samples["apa"]["bibliography"]] == ["Doe", "Smith"]
    assert samples["ieee"]["bibliography"][0].startswith("[1]J. Smith")
    # every style must produce a usable sample, not an error placeholder
    assert all(s.get("parenthetical") for s in samples.values())


def test_style_samples_ignore_unrenderable_references(simple_doc):
    """A sample built from a reference citeproc cannot format would show the
    user nothing about the style."""
    for ref in simple_doc.references[:1]:
        ref.csl.pop("title")
        ref.parse_confidence = 0.1
    samples = style_samples(simple_doc)
    assert samples["apa"]["parenthetical"] == "(Doe, 2021)"
