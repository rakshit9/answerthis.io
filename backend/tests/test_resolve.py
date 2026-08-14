"""Reference resolution ladder and honesty on failure."""
from app.external import resolve
from app.external.cache import ApiError
from app.models.core import ResolutionStatus
from app.models.findings import ExternalSource
from tests.conftest import make_ref


def _src(title, year=2020, api="openalex"):
    return ExternalSource(api=api, api_id="W1", title=title, year=year,
                          authors=["J. Smith"], venue="V", doi="10.1/x",
                          url="https://openalex.org/W1", abstract="An abstract.",
                          csl={"id": "W1", "type": "article-journal", "title": title,
                               "issued": {"date-parts": [[year]]}})


def test_doi_ladder_first(monkeypatch):
    ref = make_ref(1, "Smith", "J.", 2020, "Foundations of unit testing")
    ref.parsed.doi = "10.1/x"
    monkeypatch.setattr(resolve.openalex, "by_doi",
                        lambda d: _src("Foundations of unit testing"))
    resolve.resolve_reference(ref)
    assert ref.resolution.status == ResolutionStatus.RESOLVED
    assert ref.resolution.method == "doi"
    assert ref.csl["id"] == "ref_1"                 # identity preserved
    assert ref.resolution.abstract == "An abstract."


def test_title_search_accept_and_reject(monkeypatch):
    ref = make_ref(1, "Smith", "J.", 2020, "Foundations of unit testing")
    monkeypatch.setattr(resolve.openalex, "by_title",
                        lambda t, per_page=5: [_src("Foundations of unit testing")])
    monkeypatch.setattr(resolve.semantic_scholar, "search", lambda t, limit=5: [])
    resolve.resolve_reference(ref)
    assert ref.resolution.status == ResolutionStatus.RESOLVED
    assert ref.resolution.match_score >= 0.92

    ref2 = make_ref(2, "Doe", "A.", 2021, "Completely unrelated quantum gravity")
    monkeypatch.setattr(resolve.openalex, "by_title",
                        lambda t, per_page=5: [_src("Knitting patterns weekly", 1999)])
    monkeypatch.setattr(resolve.semantic_scholar, "search",
                        lambda t, limit=5: [_src("Cooking with cheese", 2005)])
    resolve.resolve_reference(ref2)
    assert ref2.resolution.status == ResolutionStatus.UNRESOLVED
    assert ref2.csl["title"] == "Completely unrelated quantum gravity"  # untouched


def test_api_failure_is_failed_not_silent(monkeypatch):
    ref = make_ref(1, "Smith", "J.", 2020, "Foundations of unit testing")

    def boom(*a, **k):
        raise ApiError("openalex", "HTTP 429", 429)
    monkeypatch.setattr(resolve.openalex, "by_title", boom)
    monkeypatch.setattr(resolve.semantic_scholar, "search", boom)
    resolve.resolve_reference(ref)
    assert ref.resolution.status == ResolutionStatus.UNRESOLVED
    assert "429" in (ref.resolution.error or "")


def test_no_fields_is_unresolved():
    ref = make_ref(1, "X", "Y", 2020, "t")
    ref.parsed.title = None
    ref.parsed.doi = None
    ref.parsed.arxiv_id = None
    resolve.resolve_reference(ref)
    assert ref.resolution.status == ResolutionStatus.UNRESOLVED
    assert "Not enough parsed fields" in ref.resolution.error
