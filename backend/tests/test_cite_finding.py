"""Accepting a missing-work finding turns it into a reviewable proposal.

Review is read-only: it reports, it never edits. Accepting one of its
findings therefore has to go through the same road an agent edit takes —
proposal → integrity check → explicit approval — and must cite *exactly* the
source the reader looked at, not whatever a fresh search turns up.

No LLM is involved in this path, so these run with no API key configured.
"""
import pytest

from app.agent import apply as apply_mod
from app.agent.commands import cite_finding
from app.models.edits import ProposalStatus
from app.models.findings import ExternalSource, Finding, FindingType

CLAIM = "We apply standard methodology with no citations yet."


def _source(title="Mutation testing revisited", doi="10.1000/mut") -> ExternalSource:
    return ExternalSource(
        api="openalex", api_id="W123", title=title, year=2022,
        authors=["Ada Lovelace"], venue="Journal of Testing", doi=doi,
        url="https://openalex.org/W123", abstract="We revisit mutation testing.",
        csl={"type": "article-journal", "title": title,
             "author": [{"family": "Lovelace", "given": "Ada"}],
             "issued": {"date-parts": [[2022]]}})


def _finding(source=None, claim=CLAIM, section_id="sec_3") -> Finding:
    return Finding(
        type=FindingType.MISSING_WORK, severity="medium",
        title="Possibly missing citation: “Mutation testing revisited” (2022)",
        section_id=section_id, section_title="Methods", claim_text=claim,
        source=source if source is not None else _source())


def test_accepting_a_finding_proposes_citing_that_exact_source(simple_doc):
    prop = cite_finding(simple_doc, _finding())

    assert prop.status == ProposalStatus.PROPOSED
    assert prop.integrity.ok, prop.integrity.violations
    [ref] = prop.new_references
    assert ref.csl["title"] == "Mutation testing revisited"
    # provenance is what integrity rule I3 requires of any added reference
    assert ref.resolution.source == "openalex"
    assert ref.resolution.source_url == "https://openalex.org/W123"
    assert ref.resolution.method == "review_finding"

    [change] = prop.changes
    assert change.section_id == "sec_3"
    assert f"[[citep:{ref.id}]]" not in change.before
    # attached to the end of the sentence the finding was raised against
    assert f"{CLAIM[:-1]} [[citep:{ref.id}]]." in change.after


def test_applying_it_puts_the_reference_in_the_document(simple_doc):
    prop = cite_finding(simple_doc, _finding())
    before = len(simple_doc.references)

    report = apply_mod.apply_proposal(simple_doc, prop, [prop.changes[0].id])

    assert report.ok
    assert len(simple_doc.references) == before + 1
    added = simple_doc.references[-1]
    assert added.added_by == "agent"
    assert "Accepted review finding" in (added.added_reason or "")
    assert f"[[citep:{added.id}]]" in simple_doc.section_by_id("sec_3").content


def test_existing_citations_are_untouched(simple_doc):
    intro_before = simple_doc.section_by_id("sec_2").content
    prop = cite_finding(simple_doc, _finding())
    apply_mod.apply_proposal(simple_doc, prop, [prop.changes[0].id])

    assert simple_doc.section_by_id("sec_2").content == intro_before


# ------------------------------------------------------------- refusals --

def test_a_work_already_cited_is_refused_rather_than_duplicated(simple_doc):
    cited = simple_doc.references[0]
    src = _source(title=cited.csl["title"], doi=None)

    prop = cite_finding(simple_doc, _finding(source=src))

    assert prop.status == ProposalStatus.FAILED
    assert "already in the reference list" in prop.error
    assert not prop.new_references


def test_finding_without_a_source_is_refused(simple_doc):
    prop = cite_finding(simple_doc, _finding(source=None))
    # a Finding with source=None — nothing real to cite
    prop_no_src = cite_finding(simple_doc, Finding(
        type=FindingType.MISSING_WORK, section_id="sec_3", claim_text=CLAIM,
        title="no source"))
    assert prop_no_src.status == ProposalStatus.FAILED
    assert "no external source" in prop_no_src.error
    assert prop.status == ProposalStatus.PROPOSED   # control: source present


def test_a_claim_that_has_since_changed_is_refused_not_guessed(simple_doc):
    """The anchor sentence is gone, so there is nowhere safe to attach the
    citation. Attaching it somewhere approximate would silently move the
    reader's intent onto a different statement."""
    prop = cite_finding(simple_doc, _finding(
        claim="A sentence that appears nowhere in this paper at all."))

    assert prop.status == ProposalStatus.FAILED
    assert "nowhere safe" in prop.error


def test_unknown_section_is_refused(simple_doc):
    prop = cite_finding(simple_doc, _finding(section_id="sec_does_not_exist"))
    assert prop.status == ProposalStatus.FAILED
    assert "no longer exists" in prop.error


@pytest.mark.parametrize("kind", [FindingType.CLAIM_MISMATCH,
                                  FindingType.SEARCH_FAILURE])
def test_non_missing_work_findings_still_need_a_source(simple_doc, kind):
    """The endpoint gates on type; the function gates on substance. A finding
    with a real source and a real anchor is citable whatever its label."""
    f = _finding()
    f.type = kind
    prop = cite_finding(simple_doc, f)
    assert prop.status == ProposalStatus.PROPOSED
