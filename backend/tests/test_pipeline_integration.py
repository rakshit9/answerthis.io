"""End-to-end parse of a synthetic PDF built with reportlab.

This keeps the integration test hermetic (no network, no bundled real
paper) while exercising the full A→E pipeline on an actual PDF file.
"""
import pytest
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.parsing.pipeline import parse_pdf

BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=13)
H1 = ParagraphStyle("h1", fontName="Times-Bold", fontSize=13, leading=16,
                    spaceBefore=10, spaceAfter=6)
TITLE = ParagraphStyle("title", fontName="Times-Bold", fontSize=17, leading=20)
REF = ParagraphStyle("ref", fontName="Times-Roman", fontSize=9, leading=12,
                     leftIndent=18, firstLineIndent=-18)


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdf") / "synthetic.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=LETTER)
    story = [
        Paragraph("Synthetic Papers Considered Harmful", TITLE),
        Spacer(1, 8),
        Paragraph("Alice Author, Bob Builder", BODY),
        Spacer(1, 12),
        Paragraph("Abstract", H1),
        Paragraph("We synthesize a small paper to test a parsing pipeline. "
                  "The abstract mentions structured extraction and citations.", BODY),
        Paragraph("1 Introduction", H1),
        Paragraph("Parsing PDFs is hard [1]. Layout analysis helps [2]. "
                  "Both problems interact [1, 2]. This paragraph exists to "
                  "carry in-text citations for the integration test.", BODY),
        Paragraph("2 Method", H1),
        Paragraph("We apply heuristics with confidence scores throughout the "
                  "processing pipeline and surface all failures to users.", BODY),
        Paragraph("References", H1),
        Paragraph("[1] J. Smith and A. Doe, “Parsing portable documents,” "
                  "in Proc. DocEng, 2019, pp. 1-8.", REF),
        Paragraph("[2] L. Chen, “Layout analysis at scale,” Journal of "
                  "Document Engineering, vol. 12, pp. 33-41, 2021.", REF),
    ]
    doc.build(story)
    return str(path)


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
