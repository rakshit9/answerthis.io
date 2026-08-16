"""Stage A′ of the parsing pipeline: capture floats (figures, tables,
boxed panels) out of the prose flow.

Problem: a PDF has no "figure" or "table" objects — just positioned text
and graphics. Without this stage, the text inside a framed definition box
or under a figure bleeds into the surrounding section as garbled prose.

Approach (deterministic, layout-evidence based — same ethos as A–E):

  A′1. Candidate regions per page, in claim-priority order:
       - ruled tables via PyMuPDF ``page.find_tables()`` (grid evidence);
       - drawn boxes: stroked/filled rectangles from ``page.get_drawings()``
         large enough to hold text, with nested/adjacent rects merged
         (a tcolorbox renders as an outer border rect + inner fill rect);
       - image zones (raster/vector figure bodies) from block type 1.
  A′2. Claim text lines whose center falls inside a region. Claimed lines
       are *preserved* on the float and *excluded* from section prose.
  A′3. Captions: lines matching ``Figure N.`` / ``Table N.`` are attached
       to the nearest region above or below in the same column; a caption
       with no region becomes a caption-only float and a warning — the
       failure is surfaced, never hidden.
  A′4. Each float records the last prose line before it in reading order,
       so the pipeline can attach it to the section whose text surrounds it.

The honest contract: nothing is dropped. Text either stays prose or moves
onto a float; both are visible in the UI. Visual layout inside a float is
NOT reconstructed and the UI says so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

from ..models.core import FloatKind, ParseWarning
from .pdf_extract import ExtractedDoc, Line
from .structure import flatten_lines

_CAPTION_RE = re.compile(r"^(Figure|Fig\.|Table)\s+(\d+)\s*[.:]", re.I)

MIN_BOX_W = 90.0          # pt — smaller rects are rules/underlines
MIN_BOX_H = 24.0          # pt — at least ~2 text lines
MAX_BOX_PAGE_FRAC = 0.9   # a rect covering ~the whole page is a border, not a box
MERGE_GAP = 14.0          # pt — stacked panels closer than this merge into one float
CAPTION_ATTACH_GAP = 40.0 # pt — max caption↔region distance


@dataclass
class RawFloat:
    kind: FloatKind
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    lines: list[Line] = field(default_factory=list)
    caption_lines: list[Line] = field(default_factory=list)
    table_text: str = ""            # pre-extracted rows for ruled tables

    def overlaps(self, other: "RawFloat") -> bool:
        return not (self.x1 <= other.x0 or other.x1 <= self.x0
                    or self.y1 <= other.y0 or other.y1 <= self.y0)


@dataclass
class FloatResult:
    floats: list[RawFloat]
    claimed_ids: set[int]           # id() of every Line claimed by a float
    anchors: dict[int, Line | None] # float index → last prose line before it
    warnings: list[ParseWarning] = field(default_factory=list)


def _merge_rects(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Union rects that overlap or sit within MERGE_GAP vertically while
    horizontally aligned (the border/fill double-rect and stacked panels)."""
    rects = sorted(rects, key=lambda r: (r.y0, r.x0))
    out: list[pymupdf.Rect] = []
    for r in rects:
        merged = False
        for i, o in enumerate(out):
            h_overlap = min(r.x1, o.x1) - max(r.x0, o.x0)
            h_align = h_overlap > 0.8 * min(r.width, o.width)
            v_close = r.y0 - o.y1 < MERGE_GAP and o.y0 - r.y1 < MERGE_GAP
            if h_align and v_close:
                out[i] = o | r          # union
                merged = True
                break
        if not merged:
            out.append(pymupdf.Rect(r))
    return out


def _center_in(ln: Line, x0: float, y0: float, x1: float, y1: float) -> bool:
    cx = (ln.x0 + ln.x1) / 2
    cy = (ln.y0 + ln.y1) / 2
    return x0 <= cx <= x1 and y0 <= cy <= y1


def detect_floats(pdf_path: str, extracted: ExtractedDoc) -> FloatResult:
    doc = pymupdf.open(pdf_path)
    floats: list[RawFloat] = []
    warnings: list[ParseWarning] = []

    lines_by_page: dict[int, list[Line]] = {}
    for ln in extracted.lines:
        lines_by_page.setdefault(ln.page, []).append(ln)

    for pno in range(doc.page_count):
        page = doc[pno]
        page_area = page.rect.width * page.rect.height
        regions: list[RawFloat] = []

        # ---- A′1a: ruled tables ---------------------------------------
        try:
            for tab in page.find_tables().tables:
                r = pymupdf.Rect(tab.bbox)
                if r.width < MIN_BOX_W or r.height < MIN_BOX_H:
                    continue
                rows = tab.extract()
                text = "\n".join(
                    " | ".join((c or "").strip() for c in row) for row in rows
                ).strip()
                regions.append(RawFloat(FloatKind.TABLE, pno, r.x0, r.y0, r.x1, r.y1,
                                        table_text=text))
        except Exception:       # table finder is best-effort
            pass

        # ---- A′1b: drawn boxes ----------------------------------------
        box_rects = []
        for d in page.get_drawings():
            r = d["rect"]
            if (r.width >= MIN_BOX_W and r.height >= MIN_BOX_H
                    and r.width * r.height < page_area * MAX_BOX_PAGE_FRAC):
                box_rects.append(pymupdf.Rect(r))
        for r in _merge_rects(box_rects):
            cand = RawFloat(FloatKind.BOX, pno, r.x0, r.y0, r.x1, r.y1)
            if not any(cand.overlaps(t) for t in regions):
                regions.append(cand)

        # ---- A′1c: image zones ----------------------------------------
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") == 1:
                bx0, by0, bx1, by1 = block["bbox"]
                if bx1 - bx0 < MIN_BOX_W or by1 - by0 < MIN_BOX_H:
                    continue
                cand = RawFloat(FloatKind.FIGURE, pno, bx0, by0, bx1, by1)
                if not any(cand.overlaps(rg) for rg in regions):
                    regions.append(cand)

        if not regions and not lines_by_page.get(pno):
            continue

        # ---- A′2: claim lines -----------------------------------------
        page_lines = lines_by_page.get(pno, [])
        for rg in regions:
            for ln in page_lines:
                if _center_in(ln, rg.x0, rg.y0, rg.x1, rg.y1) and not any(
                        ln in other.lines for other in regions):
                    rg.lines.append(ln)
        # a box region with no text and no table grid is decoration, not a float
        regions = [rg for rg in regions
                   if rg.lines or rg.table_text or rg.kind == FloatKind.FIGURE]

        # ---- A′3: captions --------------------------------------------
        claimed_here = {id(l) for rg in regions for l in rg.lines}
        for i, ln in enumerate(page_lines):
            if id(ln) in claimed_here:
                continue
            m = _CAPTION_RE.match(ln.text)
            if not m:
                continue
            cap_lines = [ln]
            # caption continuation: following unclaimed lines with a small gap
            j = page_lines.index(ln) + 1
            while j < len(page_lines):
                nxt = page_lines[j]
                if (id(nxt) not in claimed_here and not _CAPTION_RE.match(nxt.text)
                        and nxt.column == ln.column
                        and 0 <= nxt.y0 - cap_lines[-1].y1 < (ln.y1 - ln.y0) * 1.2):
                    cap_lines.append(nxt)
                    j += 1
                else:
                    break
            wants = FloatKind.TABLE if m.group(1).lower().startswith("t") else FloatKind.FIGURE
            # nearest region above or below in the same column band
            best, best_gap = None, CAPTION_ATTACH_GAP
            for rg in regions:
                h_overlap = min(ln.x1, rg.x1) - max(ln.x0, rg.x0)
                if h_overlap <= 0:
                    continue
                gap = min(abs(ln.y0 - rg.y1), abs(rg.y0 - cap_lines[-1].y1))
                if gap < best_gap:
                    best, best_gap = rg, gap
            if best is not None:
                best.caption_lines = cap_lines
                best.kind = wants          # caption names the float's true kind
            else:
                orphan = RawFloat(wants, pno, ln.x0, ln.y0, ln.x1, ln.y1,
                                  caption_lines=cap_lines)
                regions.append(orphan)
                warnings.append(ParseWarning(
                    stage="floats",
                    message=f"Caption {ln.text[:60]!r} has no detectable "
                            f"figure/table region nearby",
                    detail="Kept as a caption-only float; its body may be a "
                           "vector drawing the extractor cannot delimit."))
        floats.extend(regions)

    # ---- A′4: reading-order anchors -----------------------------------
    claimed_ids = {id(l) for f in floats for l in f.lines + f.caption_lines}
    first_claim: dict[int, int] = {}       # id(first claimed line) → float idx
    for fi, f in enumerate(floats):
        for ln in f.lines + f.caption_lines:
            first_claim.setdefault(id(ln), fi)
    anchors: dict[int, Line | None] = {}
    last_prose: Line | None = None
    for ln in extracted.lines:
        if id(ln) in claimed_ids:
            fi = first_claim.get(id(ln))
            if fi is not None and fi not in anchors:
                anchors[fi] = last_prose
        else:
            last_prose = ln
    doc.close()
    return FloatResult(floats=floats, claimed_ids=claimed_ids,
                       anchors=anchors, warnings=warnings)


def float_text(f: RawFloat) -> tuple[str, str]:
    """(caption, body text) for a raw float, layout flattened."""
    caption = flatten_lines(f.caption_lines) if f.caption_lines else ""
    body = f.table_text or flatten_lines(sorted(
        f.lines, key=lambda l: (l.page, l.y0, l.x0)))
    return caption, body
