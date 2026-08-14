"""Paper lifecycle routes: upload/parse, inspect, render, style, export."""
from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response

from .. import store
from ..cslproc.render import DocumentRenderer, list_styles
from ..export.latex import build_latex, build_zip
from ..models.core import SectionKind
from ..parsing.pipeline import parse_pdf

router = APIRouter(prefix="/api")


@router.get("/styles")
def get_styles():
    return list_styles()


@router.post("/papers")
async def upload_paper(file: UploadFile):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "PDF larger than 50 MB.")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        doc = parse_pdf(tmp_path, filename=file.filename or "paper.pdf")
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(422, f"Could not parse this PDF: {e}") from e
    store.save_pdf(doc.id, content)
    store.save_paper(doc)
    return {"id": doc.id, "title": doc.meta.title,
            "report": doc.parse_report.model_dump()}


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
    } for s in doc.sections if s.kind != SectionKind.REFERENCES]
    return {"style": rend.style_id, "sections": sections,
            "bibliography": rend.bibliography()}


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
