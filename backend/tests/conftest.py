import pytest
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.models.core import (PaperDocument, ParsedFields, Reference, Section,
                             SectionKind)
from app.parsing.pdf_extract import Line, Span

BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=13)
H1 = ParagraphStyle("h1", fontName="Times-Bold", fontSize=13, leading=16,
                    spaceBefore=10, spaceAfter=6)
TITLE = ParagraphStyle("title", fontName="Times-Bold", fontSize=17, leading=20)
REF = ParagraphStyle("ref", fontName="Times-Roman", fontSize=9, leading=12,
                     leftIndent=18, firstLineIndent=-18)


@pytest.fixture(scope="session")
def synthetic_pdf(tmp_path_factory):
    """A small real PDF built with reportlab — keeps PDF tests hermetic."""
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


def make_line(text: str, page: int = 0, x0: float = 50, y0: float = 100,
              size: float = 10, italic_part: str | None = None,
              width: float = 400) -> Line:
    spans = []
    if italic_part and italic_part in text:
        pre, post = text.split(italic_part, 1)
        if pre:
            spans.append(Span(pre, size, "Times", 0))
        spans.append(Span(italic_part, size, "Times-Italic", 2))
        if post:
            spans.append(Span(post, size, "Times", 0))
    else:
        spans = [Span(text, size, "Times", 0)]
    return Line(page, x0, y0, x0 + width, y0 + 11, 0, spans)


def make_ref(i: int, family: str, given: str, year: int, title: str,
             label: str | None = None, abstract: str | None = None) -> Reference:
    ref = Reference(
        id=f"ref_{i}", raw_text=f"{family}, {given}. {title}. {year}.",
        label=label,
        parsed=ParsedFields(authors=[f"{family}, {given}"], year=year, title=title),
        parse_confidence=0.9,
    )
    ref.csl = {"id": ref.id, "type": "article-journal", "title": title,
               "author": [{"family": family, "given": given}],
               "issued": {"date-parts": [[year]]}, "container-title": "Journal of Tests"}
    if abstract is not None:
        from app.models.core import Resolution, ResolutionStatus
        ref.resolution = Resolution(
            status=ResolutionStatus.RESOLVED, source="openalex",
            source_id=f"W{i}", source_url=f"https://openalex.org/W{i}",
            match_score=1.0, method="title_search", abstract=abstract)
    return ref


@pytest.fixture
def simple_doc() -> PaperDocument:
    doc = PaperDocument(filename="test.pdf")
    doc.meta.title = "A Study of Testing"
    doc.meta.abstract = "We study tests."
    doc.references = [
        make_ref(1, "Smith", "J.", 2020, "Foundations of unit testing", label="1",
                 abstract="We show that unit tests catch regressions early."),
        make_ref(2, "Doe", "A.", 2021, "Integration testing at scale", label="2"),
        make_ref(3, "Chen", "L.", 2019, "Property-based testing", label="3",
                 abstract="Property-based testing generates random inputs."),
    ]
    doc.sections = [
        Section(id="sec_1", title="Abstract", kind=SectionKind.ABSTRACT,
                content="We study tests."),
        Section(id="sec_2", title="Introduction", kind=SectionKind.BODY,
                content="Unit tests catch regressions early [[citep:ref_1]]. "
                        "Integration tests matter too [[citep:ref_2]]. "
                        "Chen [[citet:ref_3]] proposed property-based testing."),
        Section(id="sec_3", title="Methods", kind=SectionKind.BODY,
                content="We apply standard methodology with no citations yet. "
                        "Our framework builds on prior testing research."),
    ]
    from app.agent.apply import recompute_intext
    recompute_intext(doc)
    return doc
