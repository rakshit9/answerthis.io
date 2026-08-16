"""Upload runs the parse in the background and reports its real stages."""
import time

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app
from app.parsing.pipeline import STAGE_LABELS, parse_pdf


def test_on_stage_hook_narrates_every_documented_stage(synthetic_pdf):
    seen: list[tuple[str, str]] = []
    parse_pdf(str(synthetic_pdf), filename="s.pdf",
              on_stage=lambda k, phase, text: seen.append((k, phase)))

    keys = [k for k, _ in STAGE_LABELS]
    # every stage both starts and completes, in documented order
    assert [k for k, p in seen if p == "start"] == keys
    assert [k for k, p in seen if p == "done"] == keys


def test_done_events_carry_the_report_line(synthetic_pdf):
    events: list[str] = []
    doc = parse_pdf(str(synthetic_pdf), filename="s.pdf",
                    on_stage=lambda k, phase, text: events.append(text) if phase == "done" else None)
    # the narrated lines are exactly the report's own stage lines
    assert events == doc.parse_report.stages


def test_paper_id_can_be_pinned_before_parsing(synthetic_pdf):
    doc = parse_pdf(str(synthetic_pdf), filename="s.pdf", paper_id="fixedid00001")
    assert doc.id == "fixedid00001"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(store.settings, "data_dir", tmp_path)
    # no presentation pacing in tests
    monkeypatch.setattr(store.settings, "parse_min_seconds", 0.0)
    return TestClient(app)


def test_upload_returns_immediately_then_polls_to_done(client, synthetic_pdf):
    with open(synthetic_pdf, "rb") as fh:
        r = client.post("/api/papers", files={"file": ("s.pdf", fh, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    paper_id = body["id"]
    assert [s["key"] for s in body["stages"]] == [k for k, _ in STAGE_LABELS]

    for _ in range(100):
        st = client.get(f"/api/papers/{paper_id}/parse").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", st.get("error")
    assert [e["key"] for e in st["events"]] == [k for k, _ in STAGE_LABELS]
    assert client.get(f"/api/papers/{paper_id}").status_code == 200


def test_parse_status_404s_for_unknown_paper(client):
    assert client.get("/api/papers/nope/parse").status_code == 404


def test_non_pdf_is_rejected_before_any_job_starts(client):
    r = client.post("/api/papers", files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400
