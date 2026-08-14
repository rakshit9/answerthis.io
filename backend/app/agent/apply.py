"""Applying an approved proposal to the document.

Only the changes the user approved are applied. Integrity is re-checked on
the approved subset (approving change A but rejecting change B must not
leave a token pointing at a reference that only B introduced). A version
snapshot is taken first, so apply is always undoable.
"""
from __future__ import annotations

from ..models.core import (InTextCitation, PaperDocument, extract_token_ref_ids,
                           CITE_TOKEN_RE)
from ..models.edits import EditProposal, IntegrityReport, ProposalStatus
from ..parsing.textutil import sentence_at
from . import integrity


class ApplyError(Exception):
    def __init__(self, message: str, report: IntegrityReport | None = None):
        super().__init__(message)
        self.report = report


def apply_proposal(doc: PaperDocument, proposal: EditProposal,
                   approved_change_ids: list[str]) -> IntegrityReport:
    approved = [c for c in proposal.changes if c.id in approved_change_ids]
    if not approved:
        proposal.status = ProposalStatus.REJECTED
        return IntegrityReport(ok=True, summary="Nothing approved; document unchanged.")

    # ---- re-check integrity on the approved subset --------------------
    subset = proposal.model_copy(deep=True)
    subset.changes = [c.model_copy(deep=True) for c in approved]
    # keep only new refs that the approved text actually cites
    needed_ids = set()
    for c in subset.changes:
        needed_ids.update(extract_token_ref_ids(c.after))
    subset.new_references = [r for r in proposal.new_references if r.id in needed_ids]
    report = integrity.check_proposal(doc, subset)
    if not report.ok:
        raise ApplyError("Integrity violations in the approved subset; "
                         "refusing to apply.", report)

    # ---- stale-base guard ---------------------------------------------
    for c in approved:
        sec = doc.section_by_id(c.section_id)
        if sec is None:
            raise ApplyError(f"Section {c.section_id} no longer exists.")
        if sec.content != c.before:
            raise ApplyError(
                f"Section “{sec.title}” changed since this proposal was made "
                "(another edit was applied). Re-run the command.")

    # ---- snapshot, then mutate ----------------------------------------
    doc.snapshot(reason=f"edit: {proposal.command[:120]}", proposal_id=proposal.id)
    for c in approved:
        sec = doc.section_by_id(c.section_id)
        assert sec is not None
        sec.content = c.after
    existing = {r.id for r in doc.references}
    for ref in subset.new_references:
        if ref.id not in existing:
            doc.references.append(ref)
            existing.add(ref.id)

    recompute_intext(doc)
    proposal.status = ProposalStatus.APPLIED
    for c in proposal.changes:
        c.approved = c.id in approved_change_ids
    return report


def recompute_intext(doc: PaperDocument) -> None:
    """Rebuild the derived in-text citation records from tokens."""
    out: list[InTextCitation] = []
    for sec in doc.sections:
        for m in CITE_TOKEN_RE.finditer(sec.content):
            ids = [r.strip() for r in m.group(2).split(",") if r.strip()]
            out.append(InTextCitation(
                section_id=sec.id, raw=m.group(0), ref_ids=ids,
                context=sentence_at(sec.content, m.start())))
    doc.intext_citations = out
