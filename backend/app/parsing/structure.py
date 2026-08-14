"""Stage B: ordered styled lines → document structure.

Input : ``ExtractedDoc`` (stage A)
Output: paper metadata (title / authors / abstract) + a list of
        ``RawSection`` objects, each holding its heading, level, kind and
        the raw ``Line`` objects it spans. Body sections are flattened to
        paragraph text later (with dehyphenation and superscript
        sentinels); the references section keeps line-level layout for
        stage C segmentation.

Steps:
  B1. Title: the largest-font line block on page 1 above the abstract.
  B2. Heading candidates: short lines that are numbered ("3", "3.1", "IV.",
      "A.") and/or set larger/bolder than body text, or that match a
      whitelist of canonical section names (Introduction … References).
  B3. Abstract: an "Abstract" heading or an "Abstract—…" run-in.
  B4. Segmentation: text between consecutive headings becomes a section;
      each section is classified as abstract / body / references / other.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from ..models.core import PaperMeta, ParseWarning, SectionKind
from .pdf_extract import ExtractedDoc, Line

# canonical section names ------------------------------------------------
_KNOWN_HEADINGS = {
    "abstract": SectionKind.ABSTRACT,
    "introduction": SectionKind.BODY,
    "related work": SectionKind.BODY,
    "background": SectionKind.BODY,
    "preliminaries": SectionKind.BODY,
    "method": SectionKind.BODY, "methods": SectionKind.BODY,
    "methodology": SectionKind.BODY,
    "approach": SectionKind.BODY, "model": SectionKind.BODY,
    "model architecture": SectionKind.BODY,
    "experiments": SectionKind.BODY, "experiment": SectionKind.BODY,
    "experimental setup": SectionKind.BODY,
    "results": SectionKind.BODY, "evaluation": SectionKind.BODY,
    "discussion": SectionKind.BODY, "analysis": SectionKind.BODY,
    "limitations": SectionKind.BODY,
    "conclusion": SectionKind.BODY, "conclusions": SectionKind.BODY,
    "future work": SectionKind.BODY,
    "references": SectionKind.REFERENCES,
    "bibliography": SectionKind.REFERENCES,
    "acknowledgements": SectionKind.OTHER, "acknowledgments": SectionKind.OTHER,
    "acknowledgement": SectionKind.OTHER, "acknowledgment": SectionKind.OTHER,
    "appendix": SectionKind.OTHER,
    "broader impact": SectionKind.OTHER,
    "ethics statement": SectionKind.OTHER,
}

_NUMBERING_RE = re.compile(
    r"^\s*(?:(\d+(?:\.\d+)*)\.?|([IVXLC]+)\.|([A-H])\.(?=\s))\s+(.*)$")


@dataclass
class RawSection:
    title: str
    level: int
    kind: SectionKind
    lines: list[Line] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class StructuredDoc:
    meta: PaperMeta
    sections: list[RawSection]
    body_size: float
    warnings: list[ParseWarning] = field(default_factory=list)


def _strip_numbering(text: str) -> tuple[str, int]:
    """Return (clean title, level) for a heading line."""
    m = _NUMBERING_RE.match(text)
    if m:
        if m.group(1):                     # 3 / 3.1 / 3.1.2
            level = m.group(1).count(".") + 1
        else:                              # roman or letter numbering
            level = 1
        return m.group(4).strip(), level
    return text.strip(), 1


def _is_heading(ln: Line, body_size: float) -> bool:
    text = ln.text
    if not text or len(text) > 90:
        return False
    if len(text.split()) > 12:
        return False
    lower = _strip_numbering(text)[0].lower().rstrip(".:")
    if lower in _KNOWN_HEADINGS:
        # Known names count as headings when set apart at all (bold, bigger,
        # all-caps, or numbered).
        numbered = bool(_NUMBERING_RE.match(text))
        set_apart = (ln.max_size > body_size * 1.02 or ln.mostly_bold
                     or text.isupper() or numbered)
        return set_apart
    # Unknown names must be numbered AND visually set apart.
    if _NUMBERING_RE.match(text) and text[-1] not in ".:,;" and (
            ln.max_size > body_size * 1.02 or ln.mostly_bold):
        # avoid matching list items / equations: heading text mostly letters
        title = _strip_numbering(text)[0]
        letters = sum(c.isalpha() or c.isspace() for c in title)
        return bool(title) and letters / max(1, len(title)) > 0.75
    return False


def build_structure(doc: ExtractedDoc) -> StructuredDoc:
    warnings: list[ParseWarning] = []
    lines = doc.lines
    if not lines:
        return StructuredDoc(PaperMeta(), [], doc.body_size,
                             [ParseWarning(stage="structure", message="No text found in PDF")])

    # ---- B1: title -----------------------------------------------------
    page0 = [l for l in lines if l.page == 0]
    title_size = max((l.max_size for l in page0[:40]), default=doc.body_size)
    title_lines = [l for l in page0[:40]
                   if abs(l.max_size - title_size) < 0.5 and len(l.text) > 3]
    # consecutive largest lines near the top form the title
    title = " ".join(l.text for l in title_lines[:3]).strip()
    if not title:
        warnings.append(ParseWarning(stage="structure", message="Could not identify a title"))

    # ---- B2/B3: heading scan ------------------------------------------
    heading_idx: list[tuple[int, str, int, SectionKind]] = []   # (line idx, title, level, kind)
    abstract_runin_idx: int | None = None
    for i, ln in enumerate(lines):
        text = ln.text
        # run-in abstract: "Abstract—We propose ..." / "Abstract. We ..."
        if abstract_runin_idx is None and re.match(r"^abstract\s*[—\-–\.:]\s+\S", text, re.I):
            abstract_runin_idx = i
            continue
        if _is_heading(ln, doc.body_size):
            clean, level = _strip_numbering(text)
            kind = _KNOWN_HEADINGS.get(clean.lower().rstrip(".:"), SectionKind.BODY)
            heading_idx.append((i, clean, level, kind))

    if not heading_idx:
        warnings.append(ParseWarning(
            stage="structure",
            message="No section headings detected; treating whole paper as one section"))

    # ---- B4: segmentation ---------------------------------------------
    sections: list[RawSection] = []

    first_heading = heading_idx[0][0] if heading_idx else len(lines)
    # Front matter: everything before the first heading (title, authors, run-in abstract)
    front = lines[:first_heading]

    # authors: page-0 front-matter lines below the title, above abstract,
    # skipping emails/affiliation-looking lines
    author_names: list[str] = []
    _AFFIL = re.compile(r"universit|institute|department|school|college|research|"
                        r"lab\b|labs\b|brain|deepmind|google|microsoft|facebook|meta ai|"
                        r"amazon|ibm|openai|academy|center|centre|inc\.?$|corp", re.I)
    for ln in front:
        t = ln.text
        if ln in title_lines or "@" in t or len(t) < 3 or _AFFIL.search(t):
            continue
        if re.match(r"^[A-Z][a-zA-Z\.\-']+(\s+[A-Z][a-zA-Z\.\-']+){1,4}([,∗\*†‡§¶\d\s]*)$", t):
            for part in re.split(r",|\band\b", t):
                part = re.sub(r"[∗\*†‡§¶\d]+", "", part).strip()
                if part and len(part.split()) <= 5 and part.lower() != title.lower():
                    author_names.append(part)
    author_names = author_names[:15]

    if abstract_runin_idx is not None:
        # abstract text runs from that line until the first heading
        abs_lines = [lines[abstract_runin_idx]]
        j = abstract_runin_idx + 1
        while j < first_heading:
            abs_lines.append(lines[j])
            j += 1
        sections.append(RawSection("Abstract", 1, SectionKind.ABSTRACT, abs_lines))

    for h, (idx, htitle, level, kind) in enumerate(heading_idx):
        end = heading_idx[h + 1][0] if h + 1 < len(heading_idx) else len(lines)
        body = lines[idx + 1:end]
        sec = RawSection(htitle, level, kind, body)
        if body:
            sec.page_start = body[0].page
            sec.page_end = body[-1].page
        sections.append(sec)

    # abstract via explicit heading wins over nothing; strip leading "Abstract—"
    meta_abstract = ""
    for sec in sections:
        if sec.kind == SectionKind.ABSTRACT:
            meta_abstract = flatten_lines(sec.lines)
            meta_abstract = re.sub(r"^abstract\s*[—\-–\.:]?\s*", "", meta_abstract, flags=re.I)
            break

    meta = PaperMeta(title=title, authors=author_names, abstract=meta_abstract)
    return StructuredDoc(meta=meta, sections=sections, body_size=doc.body_size,
                         warnings=warnings)


# --------------------------------------------------------------------------
# Flattening: styled lines → paragraph text
# --------------------------------------------------------------------------

SUP_OPEN, SUP_CLOSE = "⟨sup:", "⟩"
_SUP_CONTENT_RE = re.compile(r"^[\d,\s\-–]+$")


def flatten_lines(lines: list[Line], mark_superscripts: bool = False) -> str:
    """Join lines into flowing text.

    - de-hyphenates words split across lines ("optimi-" + "zation")
    - inserts paragraph breaks on vertical gaps / indents
    - optionally wraps superscript numeric runs as ``⟨sup:1,2⟩`` sentinels
      so the in-text citation stage can consider them as citation markers.
    """
    if not lines:
        return ""
    heights = [l.y1 - l.y0 for l in lines if l.y1 > l.y0]
    med_h = statistics.median(heights) if heights else 10.0

    parts: list[str] = []
    prev: Line | None = None
    for ln in lines:
        text = _line_text(ln, mark_superscripts)
        if not text:
            continue
        if prev is not None:
            same_flow = (ln.page == prev.page and ln.column == prev.column)
            gap = ln.y0 - prev.y1 if same_flow else 0.0
            new_para = same_flow and gap > med_h * 0.85
            if new_para:
                parts.append("\n\n")
            else:
                if parts and parts[-1].endswith("-") and text[:1].islower():
                    parts[-1] = parts[-1][:-1]        # de-hyphenate
                else:
                    parts.append(" ")
        parts.append(text)
        prev = ln
    out = "".join(parts)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r" ?\n\n ?", "\n\n", out)
    return out.strip()


def _line_text(ln: Line, mark_superscripts: bool) -> str:
    if not mark_superscripts:
        return ln.text
    out: list[str] = []
    run: list[str] = []          # pending superscript run
    for sp in ln.spans:
        if sp.superscript and _SUP_CONTENT_RE.match(sp.text.strip() or "x") and sp.text.strip():
            run.append(sp.text.strip())
        else:
            if run:
                out.append(f"{SUP_OPEN}{','.join(run)}{SUP_CLOSE}")
                run = []
            out.append(sp.text)
    if run:
        out.append(f"{SUP_OPEN}{','.join(run)}{SUP_CLOSE}")
    return "".join(out).strip()
