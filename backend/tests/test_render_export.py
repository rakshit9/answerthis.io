"""CSL rendering and LaTeX/BibTeX export."""
from app.cslproc.render import DocumentRenderer
from app.export.bibtex import entry_to_bibtex
from app.export.latex import build_latex
from app.models.core import Reference, Section, SectionKind


def test_ieee_numeric_labels(simple_doc):
    rend = DocumentRenderer(simple_doc, "ieee")
    text = rend.render_text(simple_doc.section_by_id("sec_2").content)
    assert "[1]" in text and "[2]" in text
    bib = rend.bibliography()
    assert bib[0]["ref_id"] == "ref_1"            # first-appearance order


def test_apa_author_year_labels(simple_doc):
    rend = DocumentRenderer(simple_doc, "apa")
    text = rend.render_text(simple_doc.section_by_id("sec_2").content)
    assert "(Smith, 2020)" in text
    # narrative citet: name lives in prose, label is year-only
    assert "Chen (2019)" in text
    assert "(Chen, 2019)" not in text.split("Chen (2019)")[0][-30:]


def test_render_paragraphs_keeps_labels_joined_to_their_refs(simple_doc):
    """The reader links a citation to its bibliography entry, so the parts
    must carry ref ids — and must still reassemble into the flat rendering."""
    rend = DocumentRenderer(simple_doc, "apa")
    content = simple_doc.section_by_id("sec_2").content
    paras = rend.render_paragraphs(content)

    cited = [p for para in paras for p in para if p.get("refs")]
    assert cited, "no citation parts produced"
    assert all(p["label"] and p["refs"] for p in cited)
    assert {"ref_1", "ref_3"} <= {r for p in cited for r in p["refs"]}

    flat = "\n\n".join("".join(p.get("t") or p["label"] for p in para)
                       for para in paras)
    assert flat == rend.render_text(content)


def test_render_paragraphs_splits_on_blank_lines(simple_doc):
    rend = DocumentRenderer(simple_doc, "apa")
    paras = rend.render_paragraphs("First para [[citep:ref_1]].\n\nSecond para.")
    assert len(paras) == 2
    assert paras[1] == [{"t": "Second para."}]


def test_apa_bibliography_alphabetical(simple_doc):
    rend = DocumentRenderer(simple_doc, "apa")
    ids = [b["ref_id"] for b in rend.bibliography()]
    assert ids == ["ref_3", "ref_2", "ref_1"]     # Chen, Doe, Smith


def test_unparsed_ref_falls_back_to_raw(simple_doc):
    simple_doc.references.append(Reference(
        id="ref_9", raw_text="some unparseable garbage entry 2020",
        parse_confidence=0.2, csl={"id": "ref_9"}))
    rend = DocumentRenderer(simple_doc, "ieee")
    bib = rend.bibliography()
    raw = [b for b in bib if b["raw_fallback"]]
    assert len(raw) == 1
    assert raw[0]["formatted"] == "some unparseable garbage entry 2020"


def test_latex_export_tokens_and_escaping(simple_doc):
    simple_doc.sections.append(Section(
        id="sec_9", title="Escaping & Symbols", kind=SectionKind.BODY,
        content="We reach 95% accuracy & more [[citep:ref_1]]. F_1 too."))
    files = build_latex(simple_doc, "ieee")
    tex = files["main.tex"]
    assert r"\cite{ref_1,ref_2}" not in tex       # groups preserved as-is
    assert r"\cite{ref_1}" in tex
    assert r"95\% accuracy \& more" in tex
    assert r"F\_1" in tex
    assert r"\cite{ref\_1}" not in tex            # keys never escaped
    assert r"\begin{thebibliography}" in tex
    assert "PROVENANCE.md" in files


def test_latex_natbib_for_author_year(simple_doc):
    tex = build_latex(simple_doc, "apa")["main.tex"]
    assert r"\usepackage[round]{natbib}" in tex
    assert r"\citep{ref_1}" in tex
    assert r"\citet{ref_3}" in tex
    assert r"\bibitem[Smith(2020)]{ref_1}" in tex


def test_bibtex_serialization():
    item = {"id": "ref_1", "type": "paper-conference",
            "title": "Attention & friends", "author": [
                {"family": "Vaswani", "given": "Ashish"}],
            "issued": {"date-parts": [[2017]]},
            "container-title": "NeurIPS", "page": "5998-6008",
            "DOI": "10.1/x"}
    out = entry_to_bibtex(item)
    assert out.startswith("@inproceedings{ref_1,")
    assert r"Attention \& friends" in out
    assert "booktitle = {NeurIPS}" in out
    assert "author = {Vaswani, Ashish}" in out
    assert "pages = {5998-6008}" in out


def test_markdown_export_has_labels(simple_doc):
    md = build_latex(simple_doc, "ieee")["paper.md"]
    assert "[1]" in md
    assert "## References" in md
