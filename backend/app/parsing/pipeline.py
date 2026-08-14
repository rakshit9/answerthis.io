"""Parsing pipeline orchestrator: PDF file → ``PaperDocument``.

  A. pdf_extract.extract_document   PDF → ordered styled lines
  B. structure.build_structure      lines → title/abstract/sections
  C. reflist.segment_references     references section → raw entries
  D. refparse.parse_entry/to_csl    raw entry → fields → CSL-JSON
  E. intext.tokenize_sections       body text → [[citep/citet:…]] tokens

The resulting document carries a ``ParseReport`` that records every stage,
every warning, and exact counts of what was and wasn't parsed — the UI
shows this verbatim.
"""
from __future__ import annotations

from ..models.core import (IntextStyle, PaperDocument, ParseReport, ParseWarning,
                           Reference, Section, SectionKind)
from . import intext, pdf_extract, refparse, reflist, structure

# in-text style → default CSL style id (user can override in the UI)
STYLE_TO_CSL = {
    IntextStyle.NUMERIC_BRACKET: "ieee",
    IntextStyle.NUMERIC_SUPERSCRIPT: "nature",
    IntextStyle.AUTHOR_YEAR: "apa",
    IntextStyle.UNKNOWN: "ieee",
}

PARSE_OK_THRESHOLD = 0.5


def parse_pdf(pdf_path: str, filename: str = "") -> PaperDocument:
    report = ParseReport()
    doc = PaperDocument(filename=filename or pdf_path.rsplit("/", 1)[-1])

    # ---- A ------------------------------------------------------------
    extracted = pdf_extract.extract_document(pdf_path)
    report.n_pages = extracted.n_pages
    report.warnings.extend(extracted.warnings)
    report.stages.append(
        f"A. Extracted {len(extracted.lines)} text lines from {extracted.n_pages} pages "
        f"(body font ≈ {extracted.body_size}pt, two-column detection per page)")

    # ---- B ------------------------------------------------------------
    structured = structure.build_structure(extracted)
    report.warnings.extend(structured.warnings)
    doc.meta = structured.meta
    report.stages.append(
        f"B. Structure: title {'found' if structured.meta.title else 'NOT found'}, "
        f"abstract {'found' if structured.meta.abstract else 'NOT found'}, "
        f"{len(structured.sections)} sections")

    # ---- C ------------------------------------------------------------
    ref_secs = [s for s in structured.sections if s.kind == SectionKind.REFERENCES]
    raw_entries: list[reflist.RawEntry] = []
    seg_note = "no references section found"
    if ref_secs:
        seg = reflist.segment_references([ln for s in ref_secs for ln in s.lines])
        raw_entries = seg.entries
        seg_note = f"strategy '{seg.strategy}' (score {seg.score:.2f}), {len(seg.entries)} entries"
        for n in seg.notes:
            if "Could not segment" in n:
                report.warnings.append(ParseWarning(stage="reflist", message=n))
    else:
        report.warnings.append(ParseWarning(
            stage="reflist", message="No references/bibliography section was detected"))
    report.stages.append(f"C. Reference list segmentation: {seg_note}")

    # ---- D ------------------------------------------------------------
    references: list[Reference] = []
    for i, entry in enumerate(raw_entries, start=1):
        fields, conf, issues = refparse.parse_entry(entry.raw_text, entry.italic_segments)
        ref_id = f"ref_{i}"
        references.append(Reference(
            id=ref_id,
            raw_text=entry.raw_text,
            label=entry.label,
            parsed=fields,
            parse_confidence=conf,
            parse_issues=issues,
            csl=refparse.to_csl(fields, ref_id, entry.raw_text),
        ))
    doc.references = references
    n_ok = sum(1 for r in references if r.parse_confidence >= PARSE_OK_THRESHOLD)
    report.n_references_found = len(references)
    report.n_references_parsed = n_ok
    report.n_references_unparsed = len(references) - n_ok
    report.stages.append(
        f"D. Parsed {n_ok}/{len(references)} reference entries into structured fields "
        f"(threshold {PARSE_OK_THRESHOLD}); {len(references) - n_ok} surfaced as unparsed")
    if len(references) - n_ok:
        report.warnings.append(ParseWarning(
            stage="refparse",
            message=f"{len(references) - n_ok} reference(s) could not be confidently parsed",
            detail="They are kept with their raw text and shown in the UI."))

    # ---- build Section models (flatten body text with sup sentinels) ---
    sections: list[Section] = []
    section_texts: dict[str, str] = {}
    for i, rs in enumerate(structured.sections, start=1):
        sid = f"sec_{i}"
        if rs.kind == SectionKind.REFERENCES:
            content = ""          # canonical refs live in doc.references
        else:
            content = structure.flatten_lines(rs.lines, mark_superscripts=True)
        sections.append(Section(
            id=sid, title=rs.title, level=rs.level, kind=rs.kind, content=content,
            page_start=rs.page_start, page_end=rs.page_end))
        if content:
            section_texts[sid] = content

    # ---- E ------------------------------------------------------------
    result = intext.tokenize_sections(section_texts, references)
    for sec in sections:
        if sec.id in result.sections_tokenized:
            sec.content = result.sections_tokenized[sec.id]
    doc.sections = sections
    doc.intext_citations = result.citations
    report.n_intext_citations = len(result.citations)
    report.n_intext_unmatched = len(result.unmatched)
    report.intext_style = result.style
    report.intext_style_confidence = result.style_confidence
    for u in result.unmatched:
        report.warnings.append(ParseWarning(
            stage="intext", message=f"Unlinked marker {u['raw']!r}", detail=u["reason"]))
    for n in result.notes:
        report.warnings.append(ParseWarning(stage="intext", message=n))
    report.stages.append(
        f"E. In-text citations: {len(result.citations)} marker groups linked "
        f"(style: {result.style.value}, confidence {result.style_confidence}); "
        f"{len(result.unmatched)} unlinked markers surfaced")

    doc.csl_style = STYLE_TO_CSL[result.style]
    doc.csl_style_detected = result.style != IntextStyle.UNKNOWN and result.style_confidence >= 0.6
    doc.parse_report = report
    return doc
