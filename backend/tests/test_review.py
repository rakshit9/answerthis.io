"""Review engine: claim checks and missing-work honesty guarantees."""
from app.external.cache import ApiError
from app.llm.providers import MockProvider
from app.models.findings import ExternalSource, FindingType, Verdict
from app.review import claims, missing


def _progress(_msg):
    pass


def test_claim_check_no_llm_is_unverifiable(simple_doc):
    cits = claims.pick_citations_to_check(simple_doc, None, 5)
    assert cits
    findings = claims.check_claims(simple_doc, None, cits[:1], _progress)
    assert findings[0].type == FindingType.CLAIM_UNVERIFIABLE
    assert "No LLM provider" in findings[0].detail


def test_claim_check_verdict_mapping(simple_doc):
    llm = MockProvider([
        {"verdict": "does_not_support",
         "rationale": "The abstract is about early regression catching, not X.",
         "quote": "We show that unit tests catch regressions early.",
         "confidence": 0.9},
    ])
    cit = [c for c in simple_doc.intext_citations if "ref_1" in c.ref_ids][0]
    findings = claims.check_claims(simple_doc, llm, [cit], _progress)
    f = findings[0]
    assert f.type == FindingType.CLAIM_MISMATCH
    assert f.verdict == Verdict.DOES_NOT_SUPPORT
    assert f.severity == "high"
    assert f.evidence_quote                       # real quote kept
    assert f.source and f.source.url.startswith("https://openalex.org/")


def test_claim_check_fabricated_quote_discarded(simple_doc):
    llm = MockProvider([
        {"verdict": "supports", "rationale": "ok",
         "quote": "This sentence does not exist in the abstract at all, honestly.",
         "confidence": 0.9},
    ])
    cit = [c for c in simple_doc.intext_citations if "ref_1" in c.ref_ids][0]
    f = claims.check_claims(simple_doc, llm, [cit], _progress)[0]
    assert f.evidence_quote is None
    assert "not found in the abstract" in (f.verdict_rationale or "")


def test_claim_check_unresolved_ref_honest(simple_doc, monkeypatch):
    # ref_2 has no abstract; make resolution a no-op that stays unresolved
    from app.models.core import Resolution, ResolutionStatus
    ref2 = simple_doc.ref_by_id("ref_2")
    ref2.resolution = Resolution(status=ResolutionStatus.UNRESOLVED,
                                 error="No plausible match")
    llm = MockProvider([])                        # must NOT be called
    cit = [c for c in simple_doc.intext_citations if c.ref_ids == ["ref_2"]][0]
    f = claims.check_claims(simple_doc, llm, [cit], _progress)[0]
    assert f.type == FindingType.CLAIM_UNVERIFIABLE
    assert f.verdict == Verdict.CANNOT_VERIFY
    assert llm.calls == []


def _cand(title, doi=None, year=2022):
    return ExternalSource(api="openalex", api_id="W77", title=title, year=year,
                          authors=["A. Author"], venue="V", doi=doi,
                          url="https://openalex.org/W77",
                          abstract="Testing is helpful for software quality.",
                          cited_by_count=10,
                          csl={"id": "W77", "title": title})


def test_missing_work_dedupes_existing(simple_doc, monkeypatch):
    dup = _cand("Foundations of unit testing", year=2020)     # already ref_1
    fresh = _cand("A totally new testing paper about software quality")
    monkeypatch.setattr(missing.openalex, "search", lambda q, n=8: [dup, fresh])
    monkeypatch.setattr(missing.semantic_scholar, "search", lambda q, n=8: [])
    secs = [s for s in simple_doc.sections if s.id == "sec_3"]
    secs[0].content = secs[0].content * 8          # pass the length gate
    findings = missing.find_missing_work(simple_doc, None, secs, _progress,
                                         max_queries=2)
    titles = [f.source.title for f in findings if f.type == FindingType.MISSING_WORK]
    assert all("Foundations of unit testing" != t for t in titles)


def test_missing_work_search_failure_is_a_finding(simple_doc, monkeypatch):
    def boom(q, n=8):
        raise ApiError("openalex", "HTTP 429 (rate limited or busy)", 429)
    monkeypatch.setattr(missing.openalex, "search", boom)
    monkeypatch.setattr(missing.semantic_scholar, "search", boom)
    secs = [s for s in simple_doc.sections if s.id == "sec_3"]
    secs[0].content = secs[0].content * 8
    findings = missing.find_missing_work(simple_doc, None, secs, _progress,
                                         max_queries=1)
    assert any(f.type == FindingType.SEARCH_FAILURE for f in findings)
    fails = [f for f in findings if f.type == FindingType.SEARCH_FAILURE]
    assert "429" in fails[0].detail


def test_heuristic_provenance_is_labelled(simple_doc):
    sec = [s for s in simple_doc.sections if s.id == "sec_3"][0]
    sec.content = ("software testing methodology " * 30)
    qs = missing.build_queries_heuristic(simple_doc, sec)
    assert qs
    assert "no LLM" in qs[0]["method"]
