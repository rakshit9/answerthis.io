"""Stage C: reference-list segmentation strategies."""
from app.parsing.reflist import segment_references
from tests.conftest import make_line


def test_numbered_bracket_segmentation():
    lines = [
        make_line("[1] A. Author, \"First paper,\" in Proc. Conf, 2020.", y0=100),
        make_line("[2] B. Author, \"Second paper,\" in Proc. Conf, 2021,", y0=112),
        make_line("with a continuation line.", y0=124),
        make_line("[3] C. Author, \"Third paper,\" Journal, 2019.", y0=136),
    ]
    seg = segment_references(lines)
    assert seg.strategy == "numbered"
    assert [e.label for e in seg.entries] == ["1", "2", "3"]
    assert "continuation line" in seg.entries[1].raw_text
    assert seg.entries[1].raw_text.startswith("B. Author")   # marker stripped


def test_hanging_indent_segmentation():
    lines = [
        make_line("Author, A. First paper on things. Journal, 2020.", x0=50, y0=100),
        make_line("Author, B. Second paper with a very long title that", x0=50, y0=112),
        make_line("wraps to the next line. Journal, 2021.", x0=65, y0=124),
        make_line("Author, C. Third paper. Journal, 2019.", x0=50, y0=136),
    ]
    seg = segment_references(lines)
    assert seg.strategy == "hanging_indent"
    assert len(seg.entries) == 3
    assert "wraps to the next line" in seg.entries[1].raw_text


def test_hyphen_rejoined_across_lines():
    lines = [
        make_line("[1] J. Gehring et al. Convolu-", y0=100),
        make_line("tional sequence learning. In ICML, 2017.", y0=112),
        make_line("[2] Someone Else. Another entry title. In ICML, 2018.", y0=124),
        make_line("[3] Third Person. Third entry title. In ICML, 2019.", y0=136),
    ]
    seg = segment_references(lines)
    assert "Convolutional sequence" in seg.entries[0].raw_text


def test_unsegmentable_is_surfaced():
    lines = [make_line("just one weird blob of text with no structure", y0=100)]
    seg = segment_references(lines)
    assert seg.strategy == "none"
    assert seg.score == 0.0
    assert seg.entries                     # kept, not dropped
    assert any("Could not segment" in n for n in seg.notes)


def test_italic_segments_captured():
    lines = [
        make_line("Author, A. A title. Journal of Physics, 2020.", y0=100,
                  italic_part="Journal of Physics"),
        make_line("Author, B. Other title. Other Journal, 2021.", y0=112),
        make_line("Author, C. Third title. Third Journal, 2022.", y0=124),
    ]
    seg = segment_references(lines)
    assert any("Journal of Physics" in i for i in seg.entries[0].italic_segments)
