"""Action routes: reference resolution, peer review, agentic editing.

Long-running work runs in daemon threads and persists progress via the
store; the frontend polls. Nothing blocks the upload/inspect flow.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException

from .. import store
from ..agent import apply as apply_mod
from ..agent import commands
from ..config import settings
from ..external.resolve import resolve_reference
from ..llm.providers import build_provider
from ..models.core import ResolutionStatus
from ..models.edits import ProposalStatus
from ..models.findings import ReviewRun, ReviewStatus
from ..review.engine import run_review

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    llm = build_provider()
    return {
        "llm": llm.label if llm else None,
        "llm_hint": None if llm else
            "Set OPENAI_API_KEY or GEMINI_API_KEY to enable claim checks and editing.",
        "semantic_scholar_key": bool(settings.semantic_scholar_api_key),
    }


# ---------------------------------------------------------------- resolve --

@router.post("/papers/{paper_id}/resolve")
def start_resolve(paper_id: str):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    todo = [r.id for r in doc.references
            if r.resolution.status == ResolutionStatus.NOT_ATTEMPTED]

    def work():
        with store.lock_for(paper_id):
            d = store.load_paper(paper_id)
            if d is None:
                return
            for i, ref in enumerate(d.references):
                if ref.resolution.status == ResolutionStatus.NOT_ATTEMPTED:
                    resolve_reference(ref)
                    if (i + 1) % 3 == 0:
                        store.save_paper(d)
            store.save_paper(d)

    if todo:
        threading.Thread(target=work, daemon=True).start()
    return {"started": bool(todo), "todo": len(todo)}


@router.get("/papers/{paper_id}/resolve/status")
def resolve_status(paper_id: str):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    counts: dict[str, int] = {}
    for r in doc.references:
        counts[r.resolution.status.value] = counts.get(r.resolution.status.value, 0) + 1
    return {"counts": counts, "total": len(doc.references),
            "done": counts.get("not_attempted", 0) == 0}


# ----------------------------------------------------------------- review --

@router.post("/papers/{paper_id}/review")
def start_review(paper_id: str, body: dict | None = None):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    run = ReviewRun(paper_id=paper_id, scope=body or {})
    store.save_review(run)

    def work():
        with store.lock_for(paper_id):
            d = store.load_paper(paper_id)
            if d is None:
                return
            run_review(d, run, save=lambda: (store.save_review(run),
                                             store.save_paper(d)))

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": run.id, "status": run.status.value}


@router.get("/papers/{paper_id}/review/{run_id}")
def get_review(paper_id: str, run_id: str):
    run = store.load_review(paper_id, run_id)
    if run is None:
        raise HTTPException(404, "No such review run")
    return run.model_dump()


@router.get("/papers/{paper_id}/reviews")
def get_reviews(paper_id: str):
    return [r.model_dump() for r in store.list_reviews(paper_id)]


# ------------------------------------------------------------------- edit --

@router.post("/papers/{paper_id}/edit")
def start_edit(paper_id: str, body: dict):
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    command = (body.get("command") or "").strip()
    if not command:
        raise HTTPException(400, "Empty command")
    # placeholder proposal so the UI can poll while the agent works
    from ..models.edits import EditProposal
    pending = EditProposal(paper_id=paper_id, command=command,
                           status=ProposalStatus.RUNNING)
    store.save_proposal(pending)

    def work():
        d = store.load_paper(paper_id)
        if d is None:
            return
        prop = commands.handle_command(d, command)
        prop.id = pending.id          # keep the id the client is polling
        store.save_proposal(prop)

    threading.Thread(target=work, daemon=True).start()
    return {"proposal_id": pending.id, "status": pending.status.value}


@router.post("/papers/{paper_id}/reviews/{run_id}/findings/{finding_id}/cite")
def cite_finding(paper_id: str, run_id: str, finding_id: str):
    """Accept a missing-work finding: propose citing exactly that source.

    Returns a normal proposal, so it lands in the same diff + approve flow as
    an agent edit — accepting a finding is not the same as applying it.
    """
    doc = store.load_paper(paper_id)
    if doc is None:
        raise HTTPException(404, "No such paper")
    run = store.load_review(paper_id, run_id)
    if run is None:
        raise HTTPException(404, "No such review run")
    finding = next((f for f in run.findings if f.id == finding_id), None)
    if finding is None:
        raise HTTPException(404, "No such finding in that review run")

    with store.lock_for(paper_id):
        prop = commands.cite_finding(doc, finding)
        store.save_proposal(prop)
    if prop.status == ProposalStatus.FAILED:
        raise HTTPException(409, detail={"message": prop.error,
                                         "proposal_id": prop.id})
    return prop.model_dump()


@router.get("/papers/{paper_id}/proposals/{prop_id}")
def get_proposal(paper_id: str, prop_id: str):
    prop = store.load_proposal(paper_id, prop_id)
    if prop is None:
        raise HTTPException(404, "No such proposal")
    return prop.model_dump()


@router.get("/papers/{paper_id}/proposals")
def get_proposals(paper_id: str):
    return [p.model_dump() for p in store.list_proposals(paper_id)]


@router.post("/papers/{paper_id}/proposals/{prop_id}/apply")
def apply_proposal(paper_id: str, prop_id: str, body: dict):
    prop = store.load_proposal(paper_id, prop_id)
    if prop is None:
        raise HTTPException(404, "No such proposal")
    if prop.status not in (ProposalStatus.PROPOSED,):
        raise HTTPException(409, f"Proposal is {prop.status.value}, not applicable")
    approved = body.get("approved_change_ids") or []
    with store.lock_for(paper_id):
        doc = store.load_paper(paper_id)
        if doc is None:
            raise HTTPException(404, "No such paper")
        try:
            report = apply_mod.apply_proposal(doc, prop, approved)
        except apply_mod.ApplyError as e:
            store.save_proposal(prop)
            raise HTTPException(409, detail={
                "message": str(e),
                "report": e.report.model_dump() if e.report else None}) from e
        store.save_paper(doc)
        store.save_proposal(prop)
    return {"status": prop.status.value, "report": report.model_dump(),
            "version": doc.version}


@router.post("/papers/{paper_id}/proposals/{prop_id}/reject")
def reject_proposal(paper_id: str, prop_id: str):
    prop = store.load_proposal(paper_id, prop_id)
    if prop is None:
        raise HTTPException(404, "No such proposal")
    prop.status = ProposalStatus.REJECTED
    store.save_proposal(prop)
    return {"status": prop.status.value}
