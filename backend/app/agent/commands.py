"""Agent orchestrator: command in → EditProposal out.

  1. plan     (planner.make_plan — typed ops, validated)
  2. execute  (operations.op_* — searches, drafts; everything logged)
  3. check    (integrity.check_proposal — blocking violations surface)

The proposal is returned for the user to inspect and approve; ``apply``
happens in a separate call.
"""
from __future__ import annotations

import re

from ..llm.providers import build_provider
from ..models.core import PaperDocument
from ..models.edits import AgentStep, EditProposal, ProposalStatus, SectionChange
from . import integrity, operations, planner


def handle_command(doc: PaperDocument, command: str) -> EditProposal:
    proposal = EditProposal(paper_id=doc.id, command=command)
    llm = build_provider()
    proposal.llm_used = llm.label if llm else None

    if llm is None:
        proposal.status = ProposalStatus.FAILED
        proposal.error = ("Agentic editing needs an LLM provider. Set "
                          "OPENAI_API_KEY or GEMINI_API_KEY (see README) — the "
                          "app will not fake an edit without one.")
        return proposal

    # ---- 1. plan ------------------------------------------------------
    try:
        plan = planner.make_plan(llm, doc, command)
    except planner.PlanError as e:
        proposal.status = ProposalStatus.FAILED
        proposal.error = str(e)
        return proposal
    proposal.plan = plan["plan"]
    proposal.steps.append(AgentStep(kind="plan", text=plan["plan"],
                                    data={"operations": plan["operations"]}))
    if not plan["operations"]:
        proposal.status = ProposalStatus.FAILED
        proposal.error = plan["plan"] or "The command didn't map to any supported operation."
        return proposal

    # ---- 2. execute ---------------------------------------------------
    next_ref_num = _next_ref_number(doc)
    # working copy of each touched section, so multiple ops can stack
    working: dict[str, str] = {}
    rationales: dict[str, list[str]] = {}

    for op in plan["operations"]:
        sec = doc.section_by_id(op["section_id"])
        if sec is None:
            continue
        base = working.get(sec.id, sec.content)
        if op["op"] == "find_citations":
            new_text, next_ref_num = operations.op_find_citations(
                doc, sec, op.get("topic", ""), op.get("max_new", 3),
                llm, proposal, base, next_ref_num)
            if new_text != base:
                working[sec.id] = new_text
                rationales.setdefault(sec.id, []).append(
                    "Added citation(s) from live academic search")
        elif op["op"] == "rewrite_section":
            new_text = operations.op_rewrite_section(
                sec, op["instruction"], llm, proposal, base)
            if new_text is not None and new_text != base:
                working[sec.id] = new_text
                rationales.setdefault(sec.id, []).append(op["instruction"])

    for sid, after in working.items():
        sec = doc.section_by_id(sid)
        assert sec is not None
        proposal.changes.append(SectionChange(
            section_id=sid, section_title=sec.title,
            before=sec.content, after=after,
            rationale="; ".join(rationales.get(sid, []))))

    if not proposal.changes:
        proposal.status = ProposalStatus.FAILED
        proposal.error = ("The agent could not produce a safe change for this "
                          "command (see its step log for what happened and why).")
        return proposal

    # ---- 3. integrity -------------------------------------------------
    proposal.integrity = integrity.check_proposal(doc, proposal)
    proposal.steps.append(AgentStep(kind="check", text=proposal.integrity.summary))
    return proposal


def _next_ref_number(doc: PaperDocument) -> int:
    mx = 0
    for r in doc.references:
        m = re.fullmatch(r"ref_(\d+)", r.id)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1
