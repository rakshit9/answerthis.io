"""Agent flow with a scripted LLM and mocked search APIs."""
import json

from app.agent import commands
from app.llm import providers
from app.llm.providers import MockProvider
from app.models.findings import ExternalSource


def _mock_search(monkeypatch, results):
    from app.agent import operations
    monkeypatch.setattr(operations.openalex, "search", lambda q, n=6: results)
    monkeypatch.setattr(operations.semantic_scholar, "search", lambda q, n=6: [])


def _src(title="Mutation testing in practice", year=2022):
    return ExternalSource(
        api="openalex", api_id="W123", title=title, year=year,
        authors=["Pat Tester"], venue="Testing Journal", doi="10.1/tst",
        url="https://openalex.org/W123", abstract="We study mutation testing.",
        cited_by_count=42,
        csl={"id": "W123", "type": "article-journal", "title": title,
             "author": [{"family": "Tester", "given": "Pat"}],
             "issued": {"date-parts": [[year]]}})


def test_rewrite_preserves_tokens(simple_doc, monkeypatch):
    shorter = ("Unit tests catch regressions [[citep:ref_1]]; integration tests "
               "matter [[citep:ref_2]]. Chen [[citet:ref_3]] proposed "
               "property-based testing.")
    llm = MockProvider([
        {"plan": "Shorten the introduction.",
         "operations": [{"op": "rewrite_section", "section_id": "sec_2",
                         "instruction": "make it shorter"}]},
        {"text": shorter, "rationale": "condensed"},
    ])
    monkeypatch.setattr(providers, "build_provider", lambda: llm)
    monkeypatch.setattr(commands, "build_provider", lambda: llm)
    prop = commands.handle_command(simple_doc, "make the intro shorter")
    assert prop.status.value == "proposed"
    assert prop.integrity.ok
    assert prop.changes[0].after == shorter
    assert sorted(prop.changes[0].citations_after) == ["ref_1", "ref_2", "ref_3"]


def test_rewrite_dropping_token_fails_safely(simple_doc, monkeypatch):
    bad = "Unit tests catch regressions [[citep:ref_1]]."   # drops ref_2, ref_3
    llm = MockProvider([
        {"plan": "Shorten.", "operations": [
            {"op": "rewrite_section", "section_id": "sec_2", "instruction": "shorter"}]},
        {"text": bad}, {"text": bad},        # both attempts drop tokens
    ])
    monkeypatch.setattr(commands, "build_provider", lambda: llm)
    prop = commands.handle_command(simple_doc, "make the intro shorter")
    assert prop.status.value == "failed"     # no unsafe change proposed
    assert prop.changes == []
    assert any("token mismatch" in s.text for s in prop.steps)


def test_find_citations_inserts_with_provenance(simple_doc, monkeypatch):
    llm = MockProvider([
        {"plan": "Find citations for the methods section.",
         "operations": [{"op": "find_citations", "section_id": "sec_3",
                         "topic": "testing methodology", "max_new": 2}]},
        {"claims": [{"sentence": "Our framework builds on prior testing research.",
                     "query": "software testing methodology survey"}]},
        {"ratings": [{"i": 0, "score": 3, "why": "directly relevant"}]},
    ])
    monkeypatch.setattr(commands, "build_provider", lambda: llm)
    _mock_search(monkeypatch, [_src()])
    prop = commands.handle_command(simple_doc, "find citations for the methodology")
    assert prop.status.value == "proposed"
    assert prop.integrity.ok
    assert len(prop.new_references) == 1
    new_ref = prop.new_references[0]
    assert new_ref.resolution.source_url == "https://openalex.org/W123"
    assert new_ref.added_by == "agent"
    after = prop.changes[0].after
    assert f"[[citep:{new_ref.id}]]" in after
    # inserted before the sentence-final period
    assert f"prior testing research [[citep:{new_ref.id}]]." in after
    assert prop.citation_adds[0].api == "openalex"


def test_find_citations_skips_already_cited(simple_doc, monkeypatch):
    dup = _src(title="Foundations of unit testing", year=2020)  # == ref_1
    llm = MockProvider([
        {"plan": "Add citations.", "operations": [
            {"op": "find_citations", "section_id": "sec_3", "topic": "", "max_new": 2}]},
        {"claims": [{"sentence": "Our framework builds on prior testing research.",
                     "query": "unit testing foundations"}]},
    ])
    monkeypatch.setattr(commands, "build_provider", lambda: llm)
    _mock_search(monkeypatch, [dup])
    prop = commands.handle_command(simple_doc, "add citations to methods")
    assert prop.new_references == []          # duplicate was not re-added
    assert prop.status.value == "failed"      # honest: nothing to change


def test_unplannable_command_refused(simple_doc, monkeypatch):
    llm = MockProvider([
        {"plan": "I won't invent results.", "operations": []},
    ])
    monkeypatch.setattr(commands, "build_provider", lambda: llm)
    prop = commands.handle_command(simple_doc, "fabricate better results")
    assert prop.status.value == "failed"
    assert "invent" in (prop.error or "")


def test_no_llm_is_honest(simple_doc, monkeypatch):
    monkeypatch.setattr(commands, "build_provider", lambda: None)
    prop = commands.handle_command(simple_doc, "make the intro shorter")
    assert prop.status.value == "failed"
    assert "LLM provider" in (prop.error or "")


def test_json_parse_loosely():
    from app.llm.base import parse_json_loosely
    assert parse_json_loosely('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loosely('Sure! {"a": [1, 2]} hope that helps') == {"a": [1, 2]}
    assert parse_json_loosely(json.dumps({"x": "y"})) == {"x": "y"}
