"""End-to-end parse of a synthetic PDF built with reportlab.

This keeps the integration test hermetic (no network, no bundled real
paper) while exercising the full A→E pipeline on an actual PDF file.
"""
from app.parsing.pipeline import parse_pdf

# ``synthetic_pdf`` lives in conftest.py — shared with the parse-progress tests.


def test_full_pipeline_on_synthetic_pdf(synthetic_pdf):
    doc = parse_pdf(synthetic_pdf)

    assert doc.meta.title == "Synthetic Papers Considered Harmful"
    assert "structured extraction" in doc.meta.abstract

    kinds = {s.kind.value for s in doc.sections}
    assert "references" in kinds
    titles = [s.title for s in doc.sections]
    assert "Introduction" in titles and "Method" in titles

    assert len(doc.references) == 2
    r1, r2 = doc.references
    assert r1.parsed.title == "Parsing portable documents"
    assert r1.parsed.authors == ["Smith, J.", "Doe, A."]
    assert r1.parsed.year == 2019
    assert r2.parsed.year == 2021
    assert all(r.parse_confidence >= 0.8 for r in doc.references)

    assert doc.parse_report.intext_style.value == "numeric_bracket"
    intro = [s for s in doc.sections if s.title == "Introduction"][0]
    assert "[[citep:ref_1]]" in intro.content
    assert "[[citep:ref_2]]" in intro.content
    assert "[[citep:ref_1,ref_2]]" in intro.content
    assert doc.parse_report.n_intext_unmatched == 0

    assert doc.csl_style == "ieee"          # numeric → ieee default
