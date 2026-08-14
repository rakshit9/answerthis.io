"""On-disk persistence: one directory per paper.

    data/{paper_id}/
      original.pdf
      paper.json            (canonical PaperDocument, incl. history)
      reviews/{run_id}.json
      proposals/{prop_id}.json

Plain JSON on disk keeps the data model inspectable — you can open
paper.json and see exactly what the app believes about your paper.
A per-paper re-entrant lock serializes writes from background workers.
"""
from __future__ import annotations

import threading
from pathlib import Path

from .config import settings
from .models.core import PaperDocument
from .models.edits import EditProposal
from .models.findings import ReviewRun

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def lock_for(paper_id: str) -> threading.RLock:
    with _locks_guard:
        if paper_id not in _locks:
            _locks[paper_id] = threading.RLock()
        return _locks[paper_id]


def _dir(paper_id: str) -> Path:
    return settings.data_dir / paper_id


def save_pdf(paper_id: str, content: bytes) -> Path:
    d = _dir(paper_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "original.pdf"
    p.write_bytes(content)
    return p


def save_paper(doc: PaperDocument) -> None:
    with lock_for(doc.id):
        d = _dir(doc.id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "paper.json.tmp"
        tmp.write_text(doc.model_dump_json())
        tmp.replace(d / "paper.json")


def load_paper(paper_id: str) -> PaperDocument | None:
    p = _dir(paper_id) / "paper.json"
    if not p.exists():
        return None
    return PaperDocument.model_validate_json(p.read_text())


def list_papers() -> list[dict]:
    out = []
    if not settings.data_dir.exists():
        return out
    for d in sorted(settings.data_dir.iterdir()):
        p = d / "paper.json"
        if p.exists():
            try:
                doc = PaperDocument.model_validate_json(p.read_text())
                out.append({"id": doc.id, "title": doc.meta.title,
                            "filename": doc.filename, "uploaded_at": doc.uploaded_at,
                            "n_references": len(doc.references),
                            "version": doc.version})
            except Exception:
                continue
    return sorted(out, key=lambda x: -x["uploaded_at"])


def save_review(run: ReviewRun) -> None:
    d = _dir(run.paper_id) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{run.id}.json.tmp"
    tmp.write_text(run.model_dump_json())
    tmp.replace(d / f"{run.id}.json")


def load_review(paper_id: str, run_id: str) -> ReviewRun | None:
    p = _dir(paper_id) / "reviews" / f"{run_id}.json"
    return ReviewRun.model_validate_json(p.read_text()) if p.exists() else None


def list_reviews(paper_id: str) -> list[ReviewRun]:
    d = _dir(paper_id) / "reviews"
    if not d.exists():
        return []
    runs = [ReviewRun.model_validate_json(p.read_text()) for p in d.glob("*.json")]
    return sorted(runs, key=lambda r: -r.started_at)


def save_proposal(prop: EditProposal) -> None:
    d = _dir(prop.paper_id) / "proposals"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{prop.id}.json.tmp"
    tmp.write_text(prop.model_dump_json())
    tmp.replace(d / f"{prop.id}.json")


def load_proposal(paper_id: str, prop_id: str) -> EditProposal | None:
    p = _dir(paper_id) / "proposals" / f"{prop_id}.json"
    return EditProposal.model_validate_json(p.read_text()) if p.exists() else None


def list_proposals(paper_id: str) -> list[EditProposal]:
    d = _dir(paper_id) / "proposals"
    if not d.exists():
        return []
    props = [EditProposal.model_validate_json(p.read_text()) for p in d.glob("*.json")]
    return sorted(props, key=lambda p: -p.created_at)
