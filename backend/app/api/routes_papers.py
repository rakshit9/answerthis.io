"""Paper lifecycle routes: upload/parse, inspect, render, style, export."""
from __future__ import annotations

import io
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response

from .. import store
from ..agent.apply import recompute_intext
from ..config import settings
from ..cslproc.render import DocumentRenderer, list_styles, style_samples
from ..export.latex import build_latex, build_zip
from ..models.core import SectionKind, extract_token_ref_ids
from ..parsing.pdf_extract import PdfExtractionError
from ..parsing.pipeline import STAGE_LABELS, parse_pdf

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------- parsing --
# Parsing a real paper takes seconds, so it runs in a daemon thread and the
# client polls — the same pattern resolve/review already use. Progress is the
# pipeline's own documented stages, so the UI narrates the actual algorithm
# rather than a decorative loading bar.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _job_set(paper_id: str, **fields) -> None:
    with _jobs_lock:
        _jobs.setdefault(paper_id, {}).update(fields)


def _run_parse(paper_id: str, tmp_path: str, filename: str) -> None:
    started = time.time()
    # Dwell per stage so the live view can narrate the algorithm. The real
    # work happens first; the pad only tops a stage up to its minimum.
    per_stage_min = settings.parse_min_seconds / max(1, len(STAGE_LABELS))
    stage_started = {"t": started}

    def on_stage(key: str, phase: str, text: str) -> None:
        if phase == "start":
            stage_started["t"] = time.time()
            with _jobs_lock:
                _jobs.setdefault(paper_id, {})["current"] = key
            return
        pad = per_stage_min - (time.time() - stage_started["t"])
        if pad > 0:
            time.sleep(pad)
        with _jobs_lock:
            job = _jobs.setdefault(paper_id, {})
            job["current"] = None
            job.setdefault("events", []).append(
                {"key": key, "text": text, "t": round(time.time() - started, 2)})

    try:
        doc = parse_pdf(tmp_path, filename=filename, paper_id=paper_id, on_stage=on_stage)
        store.save_paper(doc)
        _job_set(paper_id, status="done", current=None,
                 report=doc.parse_report.model_dump())
    except PdfExtractionError as e:
        # The document itself is unreadable (encrypted / no text layer). The
        # message is already written for the user — report it as-is rather
        # than wrapping it in a generic "could not parse" prefix.
        _job_set(paper_id, status="failed", current=None, error=str(e))
    except Exception as e:                                        # noqa: BLE001
        _job_set(paper_id, status="failed", current=None,
                 error=f"Could not parse this PDF: {e}")


@router.get("/styles")
def get_styles():
    return list_styles()


@router.post("/papers")
async def upload_paper(file: UploadFile):
    """Accept the PDF and start parsing; the client polls /parse for stages."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "PDF larger than 50 MB.")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    paper_id = uuid.uuid4().hex[:12]
    store.save_pdf(paper_id, content)
    _job_set(paper_id, status="running", current=None, events=[],
             filename=file.filename or "paper.pdf")
    threading.Thread(target=_run_parse, daemon=True,
                     args=(paper_id, tmp_path, file.filename or "paper.pdf")).start()
    return {"id": paper_id, "status": "running",
            "stages": [{"key": k, "label": lbl} for k, lbl in STAGE_LABELS]}


@router.get("/papers/{paper_id}/parse")
def parse_status(paper_id: str):
    with _jobs_lock:
        job = dict(_jobs.get(paper_id) or {})
    if not job:
        # Restart or an already-parsed paper: report done if it's on disk.
        if store.load_paper(paper_id) is not None:
            return {"status": "done", "current": None, "events": [],
                    "stages": [{"key": k, "label": lbl} for k, lbl in STAGE_LABELS]}
        raise HTTPException(404, "No such parse job")
    job["stages"] = [{"key": k, "label": lbl} for k, lbl in STAGE_LABELS]
    job.setdefault("events", [])
    return job


@router.get("/papers")
def papers_index():
    return store.list_papers()


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    return doc.model_dump()


@router.get("/papers/{paper_id}/rendered")
def get_rendered(paper_id: str, style: str | None = None):
    """Sections with citation tokens replaced by CSL-formatted labels, plus
    the formatted bibliography — the reader view."""
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    try:
        rend = DocumentRenderer(doc, style)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    sections = [{
        "id": s.id, "title": s.title, "level": s.level, "kind": s.kind.value,
        "html": rend.render_text(s.content),
        # Same text, but with each label still attached to its ref ids, so the
        # reader can link a citation to its bibliography entry.
        "paragraphs": rend.render_paragraphs(s.content),
    } for s in doc.sections if s.kind != SectionKind.REFERENCES]
    return {"style": rend.style_id, "sections": sections,
            "bibliography": rend.bibliography()}


@router.post("/papers/{paper_id}/sections/{section_id}")
def edit_section(paper_id: str, section_id: str, body: dict):
    """Direct manual edit of one section's text.

    Cite tokens ([[citep:ref_id]]) may be kept, moved, or deleted, but any
    token left in the text must point at a reference the paper knows —
    the same integrity floor the agent flow enforces.
    """
    content = body.get("content")
    if not isinstance(content, str):
        raise HTTPException(400, "Body must include string 'content'.")
    base_version = body.get("base_version")
    with store.lock_for(paper_id):
        doc = store.load_paper(paper_id)
        if doc is None:
            raise HTTPException(404, "No such paper")
        sec = doc.section_by_id(section_id)
        if sec is None:
            raise HTTPException(404, "No such section")
        if base_version is not None and base_version != doc.version:
            raise HTTPException(
                409, "Paper changed since you started editing (now "
                f"v{doc.version}); reload and re-apply your edit.")
        known = {r.id for r in doc.references}
        unknown = [r for r in extract_token_ref_ids(content) if r not in known]
        if unknown:
            raise HTTPException(
                409, f"Citation tokens point at unknown references: {unknown}. "
                "Keep tokens exactly as shown, or delete them.")
        if content == sec.content:
            return {"ok": True, "version": doc.version, "changed": False}
        doc.snapshot(reason=f"manual edit: {sec.title[:80]}")
        sec.content = content
        recompute_intext(doc)
        store.save_paper(doc)
    return {"ok": True, "version": doc.version, "changed": True}


_samples_cache: dict[str, tuple[int, dict]] = {}


@router.get("/papers/{paper_id}/style-samples")
def get_style_samples(paper_id: str):
    """Each available style rendered against this paper's own first cited
    references, so the export screen can show what a style switch does before
    the user commits to it. Cached per document version — the samples only
    move when the references do."""
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    cached = _samples_cache.get(paper_id)
    if cached is None or cached[0] != doc.version:
        cached = (doc.version, style_samples(doc))
        _samples_cache[paper_id] = cached
    return cached[1]


@router.post("/papers/{paper_id}/style")
def set_style(paper_id: str, body: dict):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    style = body.get("style", "")
    if style not in {s["id"] for s in list_styles()}:
        raise HTTPException(400, f"Unknown style {style!r}")
    doc.csl_style = style
    doc.csl_style_detected = False        # user override
    store.save_paper(doc)
    return {"ok": True, "style": style}


@router.get("/papers/{paper_id}/export.zip")
def export_zip(paper_id: str, style: str | None = None):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    blob = build_zip(doc, style)
    name = (doc.meta.title[:40].replace(" ", "_") or "paper") + "_revised.zip"
    return Response(blob, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/papers/{paper_id}/export/main.tex", response_class=PlainTextResponse)
def export_tex_preview(paper_id: str, style: str | None = None):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    return build_latex(doc, style)["main.tex"]
