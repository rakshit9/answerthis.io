"""The citation-integrity checker — the guarantee that edits never silently
break the paper's citations.

Checked on every proposal (before the user sees it) and again on apply
(over the approved subset):

  I1. No citation lost: per changed section, the multiset of token ref-ids
      in "after" ⊇ "before". A shortfall not covered by an explicit,
      user-visible ``CitationRemoval`` is a blocking violation.
  I2. No unknown citations: every token id in "after" must exist in the
      document's references or in the proposal's ``new_references``.
  I3. Real provenance for new refs: every agent-added reference must carry
      a resolved external source (api + clickable URL). No source → no
      insertion. This is what makes a hallucinated citation structurally
      impossible, not just discouraged.
  I4. Declared adds match reality: each ``CitationAdd`` must correspond to
      a token actually present in a changed section.
"""
from __future__ import annotations

from collections import Counter

from ..models.core import PaperDocument, extract_token_ref_ids
from ..models.edits import (EditProposal, IntegrityReport, IntegrityViolation,
                            SectionChange)


def check_change(doc: PaperDocument, proposal: EditProposal,
                 change: SectionChange) -> tuple[list[IntegrityViolation],
                                                 list[IntegrityViolation]]:
    violations: list[IntegrityViolation] = []
    warnings: list[IntegrityViolation] = []

    before = Counter(extract_token_ref_ids(change.before))
    after = Counter(extract_token_ref_ids(change.after))
    change.citations_before = sorted(before.elements())
    change.citations_after = sorted(after.elements())

    acknowledged = {r.ref_id for r in proposal.citation_removals
                    if r.section_id == change.section_id}

    # I1 — lost citations
    for ref_id, n in before.items():
        short = n - after.get(ref_id, 0)
        if short > 0:
            v = IntegrityViolation(
                kind="citation_lost",
                message=f"{ref_id} appears {short} fewer time(s) after the edit",
                section_id=change.section_id, ref_ids=[ref_id])
            if ref_id in acknowledged:
                warnings.append(v)      # explicit, user-acknowledged removal
            else:
                violations.append(v)

    # I2 — unknown refs
    known = {r.id for r in doc.references} | {r.id for r in proposal.new_references}
    for ref_id in after:
        if ref_id not in known:
            violations.append(IntegrityViolation(
                kind="unknown_ref",
                message=f"Edited text cites {ref_id}, which exists nowhere",
                section_id=change.section_id, ref_ids=[ref_id]))
    return violations, warnings


def check_proposal(doc: PaperDocument, proposal: EditProposal) -> IntegrityReport:
    report = IntegrityReport()
    for change in proposal.changes:
        v, w = check_change(doc, proposal, change)
        report.violations.extend(v)
        report.warnings.extend(w)

    # I3 — provenance of new references
    for ref in proposal.new_references:
        if not (ref.resolution.source and ref.resolution.source_url):
            report.violations.append(IntegrityViolation(
                kind="no_provenance",
                message=f"New reference {ref.id} (“{ref.csl.get('title', '?')[:60]}”) "
                        "has no external source record — refusing it",
                ref_ids=[ref.id]))

    # I4 — declared adds are real
    all_after = "".join(c.after for c in proposal.changes)
    after_ids = set(extract_token_ref_ids(all_after))
    for add in proposal.citation_adds:
        if add.ref_id not in after_ids:
            report.warnings.append(IntegrityViolation(
                kind="asserted_add_missing",
                message=f"Proposal claims to add {add.ref_id} but no token for it "
                        "exists in the edited text",
                ref_ids=[add.ref_id]))

    report.ok = not report.violations
    n_new = len(proposal.new_references)
    report.summary = (
        f"{len(proposal.changes)} section change(s); {n_new} new reference(s), "
        f"all with real source links; " if report.ok and n_new else
        f"{len(proposal.changes)} section change(s); ")
    report.summary += ("no citation-integrity violations." if report.ok
                       else f"{len(report.violations)} BLOCKING violation(s).")
    return report
