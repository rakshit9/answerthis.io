"""Direct manual section editing via POST /papers/{id}/sections/{sec_id}."""
import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app


@pytest.fixture
def client(simple_doc, monkeypatch, tmp_path):
    monkeypatch.setattr(store.settings, "data_dir", tmp_path)
    store.save_paper(simple_doc)
    return TestClient(app)


def test_edit_bumps_version_and_records_history(client, simple_doc):
    r = client.post(f"/api/papers/{simple_doc.id}/sections/sec_3",
                    json={"content": "Rewritten methods text."})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": 2, "changed": True}
    doc = store.load_paper(simple_doc.id)
    assert doc.section_by_id("sec_3").content == "Rewritten methods text."
    assert doc.version == 2
    assert doc.history[-1].reason.startswith("manual edit: Methods")


def test_citations_are_rescanned(client, simple_doc):
    # Move a citation into a previously uncited section.
    r = client.post(f"/api/papers/{simple_doc.id}/sections/sec_3",
                    json={"content": "We follow Smith [[citep:ref_1]]."})
    assert r.status_code == 200
    doc = store.load_paper(simple_doc.id)
    cites = [c for c in doc.intext_citations if c.section_id == "sec_3"]
    assert len(cites) == 1 and cites[0].ref_ids == ["ref_1"]


def test_unknown_cite_token_is_rejected(client, simple_doc):
    r = client.post(f"/api/papers/{simple_doc.id}/sections/sec_3",
                    json={"content": "Fabricated [[citep:ref_99]]."})
    assert r.status_code == 409
    assert "ref_99" in r.json()["detail"]
    # untouched
    doc = store.load_paper(simple_doc.id)
    assert doc.version == 1


def test_stale_base_version_conflicts(client, simple_doc):
    r = client.post(f"/api/papers/{simple_doc.id}/sections/sec_3",
                    json={"content": "x", "base_version": 99})
    assert r.status_code == 409
    assert "reload" in r.json()["detail"]


def test_noop_edit_does_not_bump_version(client, simple_doc):
    sec = simple_doc.section_by_id("sec_3")
    r = client.post(f"/api/papers/{simple_doc.id}/sections/sec_3",
                    json={"content": sec.content})
    assert r.status_code == 200
    assert r.json()["changed"] is False
    assert store.load_paper(simple_doc.id).version == 1


def test_missing_section_404(client, simple_doc):
    r = client.post(f"/api/papers/{simple_doc.id}/sections/nope",
                    json={"content": "x"})
    assert r.status_code == 404
