"""The citation-integrity guarantee and proposal application."""
import pytest

from app.agent import integrity
from app.agent.apply import ApplyError, apply_proposal
from app.models.core import Reference, ParsedFields, Resolution, ResolutionStatus
from app.models.edits import (CitationRemoval, EditProposal, ProposalStatus,
                              SectionChange)


def _proposal(doc, after, section_id="sec_2"):
    sec = doc.section_by_id(section_id)
    p = EditProposal(paper_id=doc.id, command="test")
    p.changes.append(SectionChange(
        section_id=section_id, section_title=sec.title,
        before=sec.content, after=after))
    return p


def test_lost_citation_blocks(simple_doc):
    p = _proposal(simple_doc, "Unit tests catch regressions early [[citep:ref_1]].")
    rep = integrity.check_proposal(simple_doc, p)
    assert not rep.ok
    kinds = {v.kind for v in rep.violations}
    assert kinds == {"citation_lost"}
    lost = {v.ref_ids[0] for v in rep.violations}
    assert lost == {"ref_2", "ref_3"}


def test_acknowledged_removal_is_warning(simple_doc):
    p = _proposal(simple_doc,
                  "Unit tests catch regressions early [[citep:ref_1]]. "
                  "Chen [[citet:ref_3]] proposed property-based testing.")
    p.citation_removals.append(CitationRemoval(
        ref_id="ref_2", section_id="sec_2", reason="user asked to drop it"))
    rep = integrity.check_proposal(simple_doc, p)
    assert rep.ok
    assert len(rep.warnings) == 1


def test_unknown_ref_blocks(simple_doc):
    sec = simple_doc.section_by_id("sec_2")
    p = _proposal(simple_doc, sec.content + " Fabricated [[citep:ref_99]].")
    rep = integrity.check_proposal(simple_doc, p)
    assert not rep.ok
    assert any(v.kind == "unknown_ref" for v in rep.violations)


def test_new_ref_without_provenance_blocks(simple_doc):
    sec = simple_doc.section_by_id("sec_2")
    p = _proposal(simple_doc, sec.content + " New claim [[citep:ref_4]].")
    p.new_references.append(Reference(
        id="ref_4", raw_text="made up", parse_confidence=1.0,
        parsed=ParsedFields(title="Some paper"), csl={"id": "ref_4", "title": "Some paper"},
        added_by="agent"))                          # NO resolution/source
    rep = integrity.check_proposal(simple_doc, p)
    assert not rep.ok
    assert any(v.kind == "no_provenance" for v in rep.violations)


def test_new_ref_with_real_source_passes(simple_doc):
    sec = simple_doc.section_by_id("sec_2")
    p = _proposal(simple_doc, sec.content + " New claim [[citep:ref_4]].")
    p.new_references.append(Reference(
        id="ref_4", raw_text="[agent-added] Real paper", parse_confidence=1.0,
        parsed=ParsedFields(title="Real paper"),
        csl={"id": "ref_4", "title": "Real paper"},
        resolution=Resolution(status=ResolutionStatus.RESOLVED,
                              source="openalex", source_id="W1",
                              source_url="https://openalex.org/W1"),
        added_by="agent"))
    rep = integrity.check_proposal(simple_doc, p)
    assert rep.ok


def test_apply_only_approved_and_versions(simple_doc):
    sec = simple_doc.section_by_id("sec_2")
    p = _proposal(simple_doc, sec.content + " Extra sentence at the end.")
    p.integrity = integrity.check_proposal(simple_doc, p)
    v0 = simple_doc.version
    report = apply_proposal(simple_doc, p, [p.changes[0].id])
    assert report.ok
    assert simple_doc.version == v0 + 1
    assert "Extra sentence" in simple_doc.section_by_id("sec_2").content
    assert p.status == ProposalStatus.APPLIED
    assert simple_doc.history[-1].reason.startswith("edit:")


def test_apply_rejects_integrity_violation(simple_doc):
    p = _proposal(simple_doc, "All citations gone.")
    with pytest.raises(ApplyError):
        apply_proposal(simple_doc, p, [p.changes[0].id])
    assert "[[citep:ref_1]]" in simple_doc.section_by_id("sec_2").content


def test_apply_stale_base_guard(simple_doc):
    sec = simple_doc.section_by_id("sec_2")
    p = _proposal(simple_doc, sec.content + " Later addition.")
    sec.content += " Concurrent change!"
    with pytest.raises(ApplyError, match="changed since"):
        apply_proposal(simple_doc, p, [p.changes[0].id])


def test_apply_prunes_unneeded_new_refs(simple_doc):
    """Rejecting the change that cites a new ref must not add that ref."""
    sec2 = simple_doc.section_by_id("sec_2")
    sec3 = simple_doc.section_by_id("sec_3")
    p = EditProposal(paper_id=simple_doc.id, command="two changes")
    p.changes.append(SectionChange(
        section_id="sec_2", section_title=sec2.title,
        before=sec2.content, after=sec2.content + " Simple addition."))
    p.changes.append(SectionChange(
        section_id="sec_3", section_title=sec3.title,
        before=sec3.content, after=sec3.content + " Cited [[citep:ref_4]]."))
    p.new_references.append(Reference(
        id="ref_4", raw_text="[agent-added] X", parse_confidence=1.0,
        parsed=ParsedFields(title="X"), csl={"id": "ref_4", "title": "X"},
        resolution=Resolution(status=ResolutionStatus.RESOLVED, source="openalex",
                              source_id="W9", source_url="https://openalex.org/W9"),
        added_by="agent"))
    apply_proposal(simple_doc, p, [p.changes[0].id])     # approve only change 1
    assert simple_doc.ref_by_id("ref_4") is None
