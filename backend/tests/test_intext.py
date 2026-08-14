"""Stage E: in-text citation detection, linking, tokenization."""
from app.models.core import IntextStyle, extract_token_ref_ids
from app.parsing.intext import tokenize_sections
from tests.conftest import make_ref


def _numbered_refs():
    return [make_ref(1, "Smith", "J.", 2020, "First work", label="1"),
            make_ref(2, "Doe", "A.", 2021, "Second work", label="2"),
            make_ref(3, "Chen", "L.", 2019, "Third work", label="3"),
            make_ref(4, "Wu", "K.", 2018, "Fourth work", label="4"),
            make_ref(5, "Li", "M.", 2017, "Fifth work", label="5")]


def _ay_refs():
    return [make_ref(1, "Smith", "J.", 2020, "First work"),
            make_ref(2, "Doe", "A.", 2021, "Second work"),
            make_ref(3, "Chen", "L.", 2019, "Third work"),
            make_ref(4, "Chen", "L.", 2019, "Third work again")]  # same author+year


def test_numeric_brackets_with_ranges():
    res = tokenize_sections(
        {"s1": "Prior work [1] and later studies [2, 3-5] agree."},
        _numbered_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_1]]" in text
    assert "[[citep:ref_2,ref_3,ref_4,ref_5]]" in text
    assert res.style == IntextStyle.NUMERIC_BRACKET
    assert len(res.citations) == 2


def test_numeric_unmatched_surfaced_not_dropped():
    res = tokenize_sections({"s1": "See [1] and the bogus [42]."}, _numbered_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_1]]" in text
    assert "[42]" in text                       # left verbatim
    assert len(res.unmatched) == 1
    assert "42" in res.unmatched[0]["reason"]


def test_author_year_parenthetical_group():
    res = tokenize_sections(
        {"s1": "Optimization is studied (Smith, 2020; Doe et al., 2021)."},
        _ay_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_1,ref_2]]" in text
    assert res.style == IntextStyle.AUTHOR_YEAR


def test_author_year_narrative_keeps_name():
    res = tokenize_sections({"s1": "Smith (2020) proposed the method."}, _ay_refs())
    text = res.sections_tokenized["s1"]
    assert text.startswith("Smith [[citet:ref_1]]")


def test_author_year_letter_disambiguation():
    res = tokenize_sections(
        {"s1": "Both variants exist (Chen, 2019a) and (Chen, 2019b)."}, _ay_refs())
    text = res.sections_tokenized["s1"]
    assert "[[citep:ref_3]]" in text
    assert "[[citep:ref_4]]" in text


def test_non_citation_parens_untouched():
    res = tokenize_sections(
        {"s1": "As shown (see Section 3) the result (accuracy 0.95) holds "
               "(Smith, 2020)."}, _ay_refs())
    text = res.sections_tokenized["s1"]
    assert "(see Section 3)" in text
    assert "(accuracy 0.95)" in text
    assert "[[citep:ref_1]]" in text


def test_superscript_needs_evidence():
    # only 1 superscript marker + no bracket style → not enough evidence,
    # sentinel is dropped rather than mis-linked
    res = tokenize_sections({"s1": "A footnote⟨sup:1⟩ here."}, _numbered_refs())
    assert "⟨sup" not in res.sections_tokenized["s1"]
    assert "[[cite" not in res.sections_tokenized["s1"]


def test_superscript_style_links_when_dominant():
    refs = _numbered_refs()
    text = ("Deep nets⟨sup:1⟩ improved vision⟨sup:2⟩ and language⟨sup:3⟩ "
            "and speech⟨sup:4,5⟩.")
    res = tokenize_sections({"s1": text}, refs)
    assert res.style == IntextStyle.NUMERIC_SUPERSCRIPT
    out = res.sections_tokenized["s1"]
    assert "[[citep:ref_1]]" in out and "[[citep:ref_4,ref_5]]" in out


def test_extract_token_ref_ids_multiset():
    ids = extract_token_ref_ids(
        "x [[citep:ref_1]] y [[citet:ref_2]] z [[citep:ref_1,ref_3]]")
    assert ids == ["ref_1", "ref_2", "ref_1", "ref_3"]
