"""Stage A′ — float capture: boxed panels, captions, and the no-drop contract.

Builds a synthetic PDF with PyMuPDF containing:
  - normal prose paragraphs,
  - a filled box (tcolorbox-style) with definition text inside,
  - a "Figure 1." caption directly under the box,
  - an orphan "Table 3." caption with no region anywhere near it.

Asserts the box text moves onto a float (out of section prose), the caption
attaches, the orphan caption is surfaced as a warning, and no text is lost.
"""
import pymupdf
import pytest

from app.models.core import FloatKind
from app.parsing.pipeline import parse_pdf

BOX_TEXT_1 = "The process of selecting and applying sequences of rules."
BOX_TEXT_2 = "Thesis 1: define, then measure the phenomena."
CAPTION = "Figure 1. Core theses of this position."
ORPHAN = "Table 3. A caption whose table the extractor cannot find."
PROSE_1 = "This paragraph is ordinary prose that must stay in the section."
PROSE_2 = "More prose after the figure, also staying in the body flow."


@pytest.fixture(scope="module")
def pdf_with_box(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdf") / "boxed.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((72, 80), "Boxed Panels Considered Harmful", fontsize=17)
    page.insert_text((72, 130), "1 Introduction", fontsize=13)
    page.insert_text((72, 155), PROSE_1, fontsize=10)

    # tcolorbox-style panel: border rect + fill rect + text inside
    outer = pymupdf.Rect(70, 180, 400, 245)
    inner = pymupdf.Rect(72, 182, 398, 243)
    page.draw_rect(outer, color=(0.6, 0.6, 0.6), fill=(0.8, 0.8, 0.8))
    page.draw_rect(inner, fill=(0.98, 0.98, 0.98))
    page.insert_text((80, 200), BOX_TEXT_1, fontsize=10)
    page.insert_text((80, 220), BOX_TEXT_2, fontsize=10)

    page.insert_text((110, 260), CAPTION, fontsize=9)
    page.insert_text((72, 300), PROSE_2, fontsize=10)
    page.insert_text((72, 500), ORPHAN, fontsize=9)

    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture(scope="module")
def parsed(pdf_with_box):
    return parse_pdf(pdf_with_box, "boxed.pdf")


def test_box_becomes_float_with_caption(parsed):
    figs = [f for f in parsed.floats if f.kind == FloatKind.FIGURE]
    assert len(figs) == 1
    f = figs[0]
    assert CAPTION in f.caption
    assert BOX_TEXT_1 in f.text and BOX_TEXT_2 in f.text
    assert f.page == 0


def test_box_text_excluded_from_prose(parsed):
    all_prose = " ".join(s.content for s in parsed.sections)
    assert BOX_TEXT_1 not in all_prose
    assert BOX_TEXT_2 not in all_prose
    assert CAPTION not in all_prose


def test_prose_survives(parsed):
    all_prose = " ".join(s.content for s in parsed.sections)
    assert PROSE_1 in all_prose
    assert PROSE_2 in all_prose


def test_orphan_caption_surfaced_not_dropped(parsed):
    orphans = [f for f in parsed.floats
               if f.kind == FloatKind.TABLE and ORPHAN in f.caption]
    assert len(orphans) == 1
    assert any(w.stage == "floats" and "no detectable" in w.message
               for w in parsed.parse_report.warnings)


def test_float_attached_to_surrounding_section(parsed):
    fig = next(f for f in parsed.floats if f.kind == FloatKind.FIGURE)
    sec = parsed.section_by_id(fig.section_id)
    assert sec is not None and sec.title.lower().startswith("introduction")


def test_report_counts_floats(parsed):
    assert parsed.parse_report.n_floats == len(parsed.floats) >= 2
    assert any("A′. Floats" in s for s in parsed.parse_report.stages)


def test_float_text_survives_latex_export(parsed):
    """Capturing a float out of prose must not delete it from the export —
    the whole point is relocation, not removal."""
    from app.export.latex import build_latex
    tex = build_latex(parsed)["main.tex"]
    assert BOX_TEXT_1.rstrip(".") in tex
    assert BOX_TEXT_2.rstrip(".") in tex
    assert r"\begin{figure}" in tex
    assert "Core theses of this position" in tex
    # the orphan caption ships too, rather than vanishing
    assert "caption whose table the extractor cannot find" in tex


def test_float_text_survives_markdown_export(parsed):
    from app.export.latex import build_markdown
    md = build_markdown(parsed)
    assert BOX_TEXT_1 in md and BOX_TEXT_2 in md


def test_float_anchored_to_skipped_section_still_exports(parsed):
    """Regression: a float can anchor to the References section, which the
    exporters skip. Its text must still ship — dropping it would silently
    lose content the parser deliberately preserved."""
    from app.export.latex import build_latex, build_markdown
    from app.models.core import Section, SectionKind

    doc = parsed.model_copy(deep=True)
    refs_sec = next((s for s in doc.sections if s.kind == SectionKind.REFERENCES), None)
    if refs_sec is None:
        refs_sec = Section(id="sec_refs", title="References", level=1,
                           kind=SectionKind.REFERENCES, content="")
        doc.sections.append(refs_sec)
    for fl in doc.floats:                      # force the pathological case
        fl.section_id = refs_sec.id

    tex = build_latex(doc)["main.tex"]
    assert "Unanchored floats" in tex
    assert BOX_TEXT_1.rstrip(".") in tex

    md = build_markdown(doc)
    assert "Unanchored floats" in md
    assert BOX_TEXT_1 in md
