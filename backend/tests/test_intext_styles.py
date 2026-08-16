"""Stage C/E: citation styles that the first pass did not cover.

Three separate gaps, all of which used to end with citations sitting in the
"couldn't parse this" bucket:

  * bracketed author–year, "[Smith et al. 2020]" (ACM, humanities)
  * parenthesised numeric, "(1)", "(1, 3)" (PNAS, ACS, AMA)
  * non-ASCII surnames — a literal ``[A-Z]`` is ASCII-only in Python, so
    Müller / Álvarez / Öztürk matched nothing at all

The non-ASCII case is tested at *both* stages on purpose: author–year linking
needs stage C to have produced references first, so fixing stage E alone would
have left the real-world case (a scanned-in APA list of European names) exactly
as broken as before.
"""
from app.models.core import IntextStyle
from app.parsing.intext import tokenize_sections
from app.parsing.reflist import segment_references
from tests.conftest import make_line, make_ref


def _numbered_refs():
    return [make_ref(1, "Smith", "J.", 2020, "First work", label="1"),
            make_ref(2, "Doe", "A.", 2021, "Second work", label="2"),
            make_ref(3, "Chen", "L.", 2019, "Third work", label="3"),
            make_ref(4, "Wu", "K.", 2018, "Fourth work", label="4")]


def _ay_refs():
    return [make_ref(1, "Smith", "J.", 2020, "First work"),
            make_ref(2, "Doe", "A.", 2021, "Second work"),
            make_ref(3, "Chen", "L.", 2019, "Third work")]


def _accented_refs():
    return [make_ref(1, "Müller", "H.", 2020, "German work"),
            make_ref(2, "Álvarez", "J.", 2021, "Spanish work"),
            make_ref(3, "Öztürk", "M.", 2019, "Turkish work")]


# ----------------------------------------------- E5: bracketed author-year --

def test_bracketed_author_year_is_linked():
    res = tokenize_sections(
        {"s1": "The approach is standard [Smith 2020] in this area."}, _ay_refs())
    assert "[[citep:ref_1]]" in res.sections_tokenized["s1"]
    assert res.style == IntextStyle.AUTHOR_YEAR


def test_bracketed_author_year_group_and_et_al():
    res = tokenize_sections(
        {"s1": "Several works agree [Smith et al. 2020; Doe and Chen 2021]."},
        _ay_refs())
    assert "[[citep:ref_1,ref_2]]" in res.sections_tokenized["s1"]


def test_numeric_brackets_are_not_stolen_by_the_author_year_matcher():
    """Regression guard: "[1, 3]" must stay with E1."""
    res = tokenize_sections({"s1": "Prior work [1] and [2, 3]."}, _numbered_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_1]]" in text
    assert "[[citep:ref_2,ref_3]]" in text
    assert res.style == IntextStyle.NUMERIC_BRACKET


def test_unlinkable_bracketed_author_year_is_surfaced_not_dropped():
    # NB: the year must be 19xx/20xx — _YEARISH ignores anything earlier, so a
    # citation of an 1890s work is invisible to the whole pipeline, not just here.
    res = tokenize_sections(
        {"s1": "Standard [Smith 2020] but also [Nobody 1999]."}, _ay_refs())
    text = res.sections_tokenized["s1"]
    assert "[Nobody 1999]" in text                 # left verbatim
    assert any("Nobody" in u["raw"] for u in res.unmatched)


# ------------------------------------------------- E4: parenthesised numeric --

def test_paren_numeric_linked_when_evidence_is_strong():
    res = tokenize_sections(
        {"s1": "Early work (1) was extended (2) and later confirmed (3, 4)."},
        _numbered_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_1]]" in text
    assert "[[citep:ref_3,ref_4]]" in text
    assert res.style == IntextStyle.NUMERIC_PAREN


def test_paren_numeric_ignored_when_it_looks_like_equation_references():
    """Two markers is not enough evidence — "(3)" is how equations are cited."""
    res = tokenize_sections(
        {"s1": "Substituting (1) into (2) gives the result."}, _numbered_refs())
    text = res.sections_tokenized["s1"]
    assert "(1)" in text and "(2)" in text         # untouched
    assert "[[citep:" not in text
    assert res.style != IntextStyle.NUMERIC_PAREN
    assert any("equation references" in n for n in res.notes)


def test_bracket_style_wins_over_paren_numbers_in_the_same_paper():
    """A paper citing "[1]" and numbering equations "(1)" must not treat the
    equation numbers as citations."""
    res = tokenize_sections(
        {"s1": "Prior work [1] and [2] and [3]. Substituting (1) into (2) and (3)."},
        _numbered_refs())
    text = res.sections_tokenized["s1"]
    assert res.style == IntextStyle.NUMERIC_BRACKET
    assert "(1)" in text and "(2)" in text and "(3)" in text
    assert text.count("[[citep:") == 3             # only the bracketed ones


# ------------------------------------------------------------- non-ASCII --

def test_author_year_links_accented_surnames():
    res = tokenize_sections(
        {"s1": "As shown (Müller, 2020) and (Álvarez, 2021) and (Öztürk, 2019)."},
        _accented_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_1]]" in text
    assert "[[citep:ref_2]]" in text
    assert "[[citep:ref_3]]" in text
    assert res.style == IntextStyle.AUTHOR_YEAR


def test_narrative_citation_with_accented_surname():
    res = tokenize_sections(
        {"s1": "Öztürk (2019) reported the same effect."}, _accented_refs())
    assert res.sections_tokenized["s1"].startswith("Öztürk [[citet:ref_3]]")


def test_reference_list_of_accented_surnames_segments():
    """The stage-C half of the same bug: without it there are no references
    for the stage-E test above to link against."""
    lines = [
        make_line("Álvarez, J. and Smith, T. A study of things. Journal, 2020.", y0=100),
        make_line("Öztürk, M. and Jones, P. Another study. Journal, 2021.", y0=112),
        make_line("Müller, H. and Brown, R. A third study. Journal, 2019.", y0=124),
    ]
    seg = segment_references(lines)
    assert seg.strategy == "author_start"
    assert len(seg.entries) == 3
    assert seg.entries[0].raw_text.startswith("Álvarez")


# ------------------------------------------ C: "(1)" reference-list markers --

def test_paren_numbered_reference_list_segments_and_strips_markers():
    lines = [
        make_line("(1) A. Author, First paper, Proc. Conf, 2020.", y0=100),
        make_line("(2) B. Author, Second paper, Proc. Conf, 2021,", y0=112),
        make_line("with a continuation line.", y0=124),
        make_line("(3) C. Author, Third paper, Journal, 2019.", y0=136),
    ]
    seg = segment_references(lines)
    assert seg.strategy == "numbered"
    assert [e.label for e in seg.entries] == ["1", "2", "3"]
    assert seg.entries[0].raw_text.startswith("A. Author")   # marker stripped
    assert "continuation line" in seg.entries[1].raw_text
