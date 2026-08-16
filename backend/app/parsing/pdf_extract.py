"""Stage A of the parsing pipeline: PDF → ordered, styled text lines.

Input : a PDF file
Output: ``ExtractedDoc`` — per-page lists of ``Line`` objects in reading
        order, with font size / bold / italic / superscript per span, plus
        the estimated body font size and any warnings.

Steps (documented, deterministic — no ML, no LLM):
  A0. Readability gate: reject an encrypted PDF, and reject a PDF with no
      extractable text layer (a scan / image-only export) with a specific
      message instead of letting it parse to an empty document. Pages that
      are individually image-only in an otherwise text-bearing PDF are kept
      and reported as a warning.
  A1. Rasterless text extraction via PyMuPDF ``page.get_text("dict")``:
      blocks → lines → spans with bbox, font name, size, style flags.
  A2. Drop rotated text (arXiv margin watermark) and out-of-flow artifacts.
  A3. Detect repeated headers/footers (same normalized text near the top or
      bottom of ≥ 35% of pages) and standalone page numbers; drop them.
  A4. Column detection per page: 1-D clustering of block x0 into 1 or 2
      columns; reading order = column-major (left column top→bottom, then
      right column).
  A5. Body font estimation: the most frequent span size across the document
      (mode), used later to tell headings (larger/bolder) from body text.
Every drop decision is recorded as a warning so the UI can show what the
extractor did.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

from ..models.core import ParseWarning

# PyMuPDF span flag bits
FLAG_SUPERSCRIPT = 1
FLAG_ITALIC = 2
FLAG_BOLD = 16

LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "’": "'", "‘": "'",
    "“": '"', "”": '"', " ": " ",
}


# A0: below this many extractable characters across the whole document there is
# nothing for stages B–E to work with. A single real page carries thousands; the
# slack absorbs repository cover stamps glued onto an otherwise-scanned PDF.
MIN_DOC_CHARS = 200


class PdfExtractionError(RuntimeError):
    """Stage-A failure caused by the *document*, not by a bug in the parser.

    Carries a message written for the person who uploaded the file — the API
    surfaces it verbatim instead of wrapping it in a generic parse error.
    """


class EncryptedPdfError(PdfExtractionError):
    """The PDF is password-protected, so no content can be read at all."""


class NoTextLayerError(PdfExtractionError):
    """The PDF carries no text layer — a scan or an image-only export.

    The counts are kept as attributes so callers can report specifics without
    having to parse the message string.
    """

    def __init__(self, message: str, *, n_pages: int, n_image_only: int, n_chars: int):
        super().__init__(message)
        self.n_pages = n_pages
        self.n_image_only = n_image_only
        self.n_chars = n_chars


def clean_text(s: str) -> str:
    for k, v in LIGATURES.items():
        s = s.replace(k, v)
    # Normalize exotic spaces/dashes but keep en-dash (used in page/citation ranges)
    s = unicodedata.normalize("NFKC", s)
    return s


@dataclass
class Span:
    text: str
    size: float
    font: str
    flags: int

    @property
    def bold(self) -> bool:
        return bool(self.flags & FLAG_BOLD) or "bold" in self.font.lower()

    @property
    def italic(self) -> bool:
        return bool(self.flags & FLAG_ITALIC) or any(
            k in self.font.lower() for k in ("italic", "oblique")
        )

    @property
    def superscript(self) -> bool:
        return bool(self.flags & FLAG_SUPERSCRIPT)


@dataclass
class Line:
    page: int              # 0-based
    x0: float
    y0: float
    x1: float
    y1: float
    column: int            # 0 = left/only column
    spans: list[Span] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans).strip()

    @property
    def max_size(self) -> float:
        return max((s.size for s in self.spans if s.text.strip()), default=0.0)

    @property
    def mostly_bold(self) -> bool:
        chars = sum(len(s.text) for s in self.spans if s.text.strip())
        bold = sum(len(s.text) for s in self.spans if s.text.strip() and s.bold)
        return chars > 0 and bold / chars > 0.6


@dataclass
class ExtractedDoc:
    lines: list[Line]                      # global reading order
    n_pages: int
    body_size: float                       # estimated body font size
    page_height: float
    warnings: list[ParseWarning] = field(default_factory=list)


_PAGE_NUM_RE = re.compile(r"^\s*(page\s+)?\d{1,4}(\s+of\s+\d{1,4})?\s*$", re.I)


def _norm_for_repeat(s: str) -> str:
    return re.sub(r"\d+", "#", s.strip().lower())


def extract_document(pdf_path: str) -> ExtractedDoc:
    doc = pymupdf.open(pdf_path)

    # ---- A0a: an encrypted PDF yields nothing; say so precisely --------
    if doc.needs_pass:
        doc.close()
        raise EncryptedPdfError(
            "This PDF is password-protected, so its text cannot be read. "
            "Remove the password and upload it again.")

    warnings: list[ParseWarning] = []
    all_pages_raw: list[list[Line]] = []
    page_height = 792.0

    # A0b bookkeeping: how much text each page yielded, and whether the page
    # carries images. A page with images and no text is a scanned page.
    page_chars: list[int] = []
    page_has_image: list[bool] = []

    n_rotated_dropped = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        page_height = page.rect.height
        pdict = page.get_text("dict")
        page_lines: list[Line] = []
        n_chars = 0
        has_image = False
        for block in pdict.get("blocks", []):
            if block.get("type") != 0:       # images
                has_image = True
                continue
            for line in block.get("lines", []):
                dx, dy = line.get("dir", (1, 0))
                if abs(dx) < 0.99:           # rotated (e.g. arXiv watermark)
                    n_rotated_dropped += 1
                    continue
                spans = [
                    Span(clean_text(s.get("text", "")), round(s.get("size", 0.0), 2),
                         s.get("font", ""), s.get("flags", 0))
                    for s in line.get("spans", [])
                ]
                joined = "".join(sp.text for sp in spans).strip()
                if not joined:
                    continue
                n_chars += len(joined)
                bx0, by0, bx1, by1 = line["bbox"]
                page_lines.append(Line(pno, bx0, by0, bx1, by1, 0, spans))
        all_pages_raw.append(page_lines)
        page_chars.append(n_chars)
        page_has_image.append(has_image)

    # ---- A0c: no text layer anywhere → refuse, with a specific reason --
    total_chars = sum(page_chars)
    image_only = [i for i, (c, img) in enumerate(zip(page_chars, page_has_image))
                  if c == 0 and img]
    if total_chars < MIN_DOC_CHARS:
        n_pages_total = doc.page_count
        doc.close()
        scanned = (f" {len(image_only)} page(s) contain only images."
                   if image_only else "")
        raise NoTextLayerError(
            f"This PDF has no extractable text layer — only {total_chars} character(s) "
            f"across {n_pages_total} page(s).{scanned} It is almost certainly a scan or "
            f"an image-only export. This app does not run OCR; OCR the file first "
            f"(for example `ocrmypdf in.pdf out.pdf`) and upload the result.",
            n_pages=n_pages_total, n_image_only=len(image_only), n_chars=total_chars)

    # ---- A0d: partially scanned → parse the rest, report the gap -------
    if image_only:
        shown = ", ".join(str(p + 1) for p in image_only[:10])
        more = f" (+{len(image_only) - 10} more)" if len(image_only) > 10 else ""
        warnings.append(ParseWarning(
            stage="extract",
            message=f"{len(image_only)} page(s) have no text layer and were not parsed",
            detail=f"Page(s) {shown}{more} contain only images — likely scanned. "
                   f"Their content is not present in the PDF as text, so nothing on "
                   f"them was extracted. OCR the file if you need it."))

    if n_rotated_dropped:
        warnings.append(ParseWarning(
            stage="extract", message=f"Dropped {n_rotated_dropped} rotated text line(s)",
            detail="Usually the arXiv margin watermark."))

    # ---- A3: repeated header/footer removal ---------------------------
    top_band = page_height * 0.10
    bot_band = page_height * 0.90
    repeat_counter: Counter[str] = Counter()
    for lines in all_pages_raw:
        seen_on_page = set()
        for ln in lines:
            if ln.y1 < top_band or ln.y0 > bot_band:
                key = _norm_for_repeat(ln.text)
                if key and key not in seen_on_page:
                    repeat_counter[key] += 1
                    seen_on_page.add(key)
    n_pages = max(1, len(all_pages_raw))
    repeated = {k for k, c in repeat_counter.items() if c >= max(2, 0.35 * n_pages)}

    n_hf_dropped = 0
    cleaned_pages: list[list[Line]] = []
    for lines in all_pages_raw:
        kept = []
        for ln in lines:
            in_band = ln.y1 < top_band or ln.y0 > bot_band
            if in_band and (_norm_for_repeat(ln.text) in repeated or _PAGE_NUM_RE.match(ln.text)):
                n_hf_dropped += 1
                continue
            kept.append(ln)
        cleaned_pages.append(kept)
    if n_hf_dropped:
        warnings.append(ParseWarning(
            stage="extract", message=f"Dropped {n_hf_dropped} header/footer line(s)",
            detail="Repeated running heads and page numbers."))

    # ---- A4: column detection + reading order -------------------------
    ordered: list[Line] = []
    for pno, lines in enumerate(cleaned_pages):
        if not lines:
            continue
        page_w = doc[pno].rect.width
        ordered.extend(_order_page(lines, page_w))

    # ---- A4b: re-join marker lines ------------------------------------
    # LaTeX headings often extract as two "lines" at the same height:
    # "3.1" and "Encoder and Decoder Stacks". Merge a bare section-number
    # line with the line immediately to its right.
    ordered = _merge_marker_lines(ordered)

    # ---- A5: body font size (mode over span character mass) -----------
    size_mass: Counter[float] = Counter()
    for ln in ordered:
        for sp in ln.spans:
            if sp.text.strip():
                size_mass[round(sp.size, 1)] += len(sp.text)
    body_size = size_mass.most_common(1)[0][0] if size_mass else 10.0

    doc.close()
    return ExtractedDoc(lines=ordered, n_pages=n_pages, body_size=body_size,
                        page_height=page_height, warnings=warnings)


_MARKER_ONLY_RE = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVXLC]{1,5}\.?|[A-H]\.)$")


def _merge_marker_lines(lines: list[Line]) -> list[Line]:
    out: list[Line] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (nxt is not None and _MARKER_ONLY_RE.match(ln.text)
                and nxt.page == ln.page
                and abs(nxt.y0 - ln.y0) < 3.0
                and 0 <= nxt.x0 - ln.x1 < 40):
            merged = Line(ln.page, ln.x0, min(ln.y0, nxt.y0), nxt.x1,
                          max(ln.y1, nxt.y1), ln.column,
                          ln.spans + [Span(" ", ln.spans[-1].size,
                                           ln.spans[-1].font, ln.spans[-1].flags)]
                          + nxt.spans)
            out.append(merged)
            i += 2
            continue
        out.append(ln)
        i += 1
    return out


def _order_page(lines: list[Line], page_w: float) -> list[Line]:
    """Detect 1 vs 2 columns from the x0 distribution and sort into
    reading order. Full-width lines (spanning both columns, e.g. the title
    block) are emitted before column content at their vertical position."""
    mid = page_w / 2
    full_width, left, right = [], [], []
    for ln in lines:
        width = ln.x1 - ln.x0
        if width > page_w * 0.6 or (ln.x0 < mid < ln.x1 and width > page_w * 0.45):
            full_width.append(ln)
        elif ln.x0 >= mid * 0.9:
            right.append(ln)
        else:
            left.append(ln)

    two_col = len(right) >= 5 and len(left) >= 5
    if not two_col:
        merged = sorted(lines, key=lambda l: (round(l.y0, 1), l.x0))
        for ln in merged:
            ln.column = 0
        return merged

    for ln in left:
        ln.column = 0
    for ln in right:
        ln.column = 1
    # Full-width lines split the page into vertical zones; within each zone
    # read left column then right column.
    full_width.sort(key=lambda l: l.y0)
    zones: list[float] = [fl.y0 for fl in full_width]
    out: list[Line] = []
    boundaries = zones + [float("inf")]
    prev_bound = -float("inf")
    fw_idx = 0
    for bound in boundaries:
        zone_left = [l for l in left if prev_bound <= l.y0 < bound]
        zone_right = [l for l in right if prev_bound <= l.y0 < bound]
        out.extend(sorted(zone_left, key=lambda l: (l.y0, l.x0)))
        out.extend(sorted(zone_right, key=lambda l: (l.y0, l.x0)))
        if fw_idx < len(full_width):
            out.append(full_width[fw_idx])
            fw_idx += 1
        prev_bound = bound
    return out
