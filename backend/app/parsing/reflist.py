"""Stage C: the references section → segmented raw entries.

Input : the ``Line`` objects of the section classified as REFERENCES
Output: ``RawEntry`` list — one per bibliography entry — with the entry's
        list label (if any), its full raw text, and italic segments (style
        hints for the field parser).

Three segmentation strategies are attempted and scored; the best one wins.
The chosen strategy and its score are reported so a bad segmentation is
visible, not silent:

  C1. Numbered markers   — entries begin "[12]" or "12." with mostly
                           monotonically increasing numbers.
  C2. Hanging indent     — entry-start lines sit at the column's left edge,
                           continuation lines are indented deeper.
  C3. Author-start       — fallback: split before lines that look like the
                           start of an author list ("Surname, F." /
                           "F. Surname" / "Surname FM,"), provided the
                           previous line looks entry-final.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .pdf_extract import Line
from .textutil import NAME_WORD, UPPER_CLASS

_NUM_BRACKET_RE = re.compile(r"^\s*\[(\d{1,3})\]\s*(.*)$")
_NUM_DOT_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.*)$")
# "(1)" / "1)" entry markers — PNAS, some ACS/AMA journals
_NUM_PAREN_RE = re.compile(r"^\s*\(?(\d{1,3})\)\s*(.*)$")
# NB: the uppercase classes are Unicode-aware (see textutil.UPPER_CLASS). With a
# literal [A-Z] here, a reference list whose entries start "Müller, H." or
# "Álvarez, J." matches nothing, scores 0, and the whole list collapses into a
# single unsegmented block.
_U = UPPER_CLASS
_AUTHOR_START_RE = re.compile(
    r"^(?:" + NAME_WORD + r",\s*(?:" + _U + r"\.[\s\-]*)+"    # Surname, F. M.
    r"|(?:" + _U + r"\.[\s\-]*)+" + NAME_WORD +               # F. M. Surname
    r"|" + NAME_WORD + r"\s+" + _U + r"{1,3}\b[,.]"           # Surname FM, (Vancouver)
    r"|" + NAME_WORD + r",?\s+" + NAME_WORD + r".*?\b(?:and|&)\b"  # Given Surname … and
    r")")
_ENTRY_FINAL_RE = re.compile(
    r"(?:\.\s*$|\d{4}[a-z]?\.?\s*$|\d+[–\-]\d+\.?\s*$|\)\s*\.?\s*$|[A-Za-z]{2,}\.\s*$)")


@dataclass
class RawEntry:
    label: str | None            # "12" for numbered lists, else None
    raw_text: str
    italic_segments: list[str] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)


@dataclass
class SegmentationResult:
    entries: list[RawEntry]
    strategy: str                # "numbered" | "hanging_indent" | "author_start" | "none"
    score: float                 # 0..1 confidence in the segmentation
    notes: list[str] = field(default_factory=list)


def _join_entry_lines(lines: list[Line]) -> tuple[str, list[str]]:
    """Merge an entry's lines into one string (de-hyphenated) and collect
    italic span texts as style hints."""
    parts: list[str] = []
    italics: list[str] = []
    ital_run: list[str] = []
    for ln in lines:
        text = ln.text
        if not text:
            continue
        if parts and parts[-1].endswith("-") and text[:1].islower():
            parts[-1] = parts[-1][:-1]
            parts.append(text)
        else:
            parts.append((" " if parts else "") + text)
        for sp in ln.spans:
            if sp.italic and sp.text.strip():
                ital_run.append(sp.text.strip())
            elif ital_run:
                italics.append(" ".join(ital_run))
                ital_run = []
    if ital_run:
        italics.append(" ".join(ital_run))
    raw = re.sub(r"\s+", " ", "".join(parts)).strip()
    return _fix_hyphens(raw), [i for i in italics if len(i) > 3]


def _fix_hyphens(s: str) -> str:
    """Rejoin words hyphen-split across lines ('Convolu- tional')."""
    return re.sub(r"([a-z])- ([a-z])", r"\1\2", s)


# ---------------------------------------------------------------- C1 ----

def _try_numbered(lines: list[Line]) -> SegmentationResult:
    groups: list[list[Line]] = []
    labels: list[int] = []
    current: list[Line] = []
    # pick the marker shape this list actually uses: "[12]", "(12)"/"12)", "12."
    by_shape = [(_NUM_BRACKET_RE, sum(1 for l in lines if _NUM_BRACKET_RE.match(l.text))),
                (_NUM_PAREN_RE, sum(1 for l in lines if _NUM_PAREN_RE.match(l.text))),
                (_NUM_DOT_RE, sum(1 for l in lines if _NUM_DOT_RE.match(l.text)))]
    rx, best_hits = max(by_shape, key=lambda p: p[1])
    if best_hits < 2:
        rx = _NUM_DOT_RE
    for ln in lines:
        m = rx.match(ln.text)
        expected = labels[-1] + 1 if labels else 1
        # accept the marker if it continues the sequence (tolerate small jumps)
        if m and abs(int(m.group(1)) - expected) <= 2:
            if current:
                groups.append(current)
            current = [ln]
            labels.append(int(m.group(1)))
        else:
            if current:
                current.append(ln)
            # text before the first marker is ignored (heading remnants)
    if current:
        groups.append(current)
    if len(groups) < 2:
        return SegmentationResult([], "numbered", 0.0)
    # score: sequence coverage + monotonicity
    mono = sum(1 for a, b in zip(labels, labels[1:]) if b == a + 1)
    score = 0.6 * (mono / max(1, len(labels) - 1)) + 0.4 * min(1.0, len(groups) / 8)
    entries = []
    for lab, grp in zip(labels, groups):
        raw, ital = _join_entry_lines(grp)
        # strip the leading marker: rebuild from the first line's post-marker
        # remainder plus the continuation lines
        m2 = rx.match(grp[0].text)
        if m2:
            raw_first = m2.group(2)
            rest_raw, _ = _join_entry_lines(grp[1:])
            joiner = "" if raw_first.endswith("-") and rest_raw[:1].islower() else " "
            raw = (raw_first.rstrip("-") if joiner == "" else raw_first)
            raw = (raw + joiner + rest_raw).strip() if rest_raw else raw.strip()
            raw = _fix_hyphens(re.sub(r"\s+", " ", raw))
        entries.append(RawEntry(str(lab), raw, ital, grp))
    return SegmentationResult(entries, "numbered", score)


# ---------------------------------------------------------------- C2 ----

def _try_hanging_indent(lines: list[Line]) -> SegmentationResult:
    # per (page, column) left edge
    edges: dict[tuple[int, int], float] = {}
    for ln in lines:
        key = (ln.page, ln.column)
        edges[key] = min(edges.get(key, 1e9), ln.x0)
    starts: list[bool] = []
    indented_seen = False
    for ln in lines:
        at_edge = ln.x0 <= edges[(ln.page, ln.column)] + 2.5
        if not at_edge:
            indented_seen = True
        starts.append(at_edge)
    if not indented_seen:
        return SegmentationResult([], "hanging_indent", 0.0,
                                  ["no indentation structure found"])
    groups: list[list[Line]] = []
    current: list[Line] = []
    for ln, is_start in zip(lines, starts):
        if is_start and current:
            groups.append(current)
            current = [ln]
        else:
            current.append(ln)
    if current:
        groups.append(current)
    if len(groups) < 3:
        return SegmentationResult([], "hanging_indent", 0.0)
    entries = []
    finals = 0
    for grp in groups:
        raw, ital = _join_entry_lines(grp)
        if _ENTRY_FINAL_RE.search(raw):
            finals += 1
        entries.append(RawEntry(None, raw, ital, grp))
    avg_len = sum(len(e.raw_text) for e in entries) / len(entries)
    score = 0.5 * (finals / len(entries)) + 0.3 * min(1.0, avg_len / 80) \
        + 0.2 * min(1.0, len(entries) / 8)
    return SegmentationResult(entries, "hanging_indent", score)


# ---------------------------------------------------------------- C3 ----

def _try_author_start(lines: list[Line]) -> SegmentationResult:
    groups: list[list[Line]] = []
    current: list[Line] = []
    for ln in lines:
        text = ln.text
        prev_final = not current or _ENTRY_FINAL_RE.search(current[-1].text or "")
        if _AUTHOR_START_RE.match(text) and prev_final and current:
            groups.append(current)
            current = [ln]
        else:
            current.append(ln)
    if current:
        groups.append(current)
    if len(groups) < 3:
        return SegmentationResult([], "author_start", 0.0)
    entries = []
    year_hits = 0
    for grp in groups:
        raw, ital = _join_entry_lines(grp)
        if re.search(r"\b(19|20)\d{2}[a-z]?\b", raw):
            year_hits += 1
        entries.append(RawEntry(None, raw, ital, grp))
    score = 0.5 * (year_hits / len(entries)) + 0.2 * min(1.0, len(entries) / 8) + 0.1
    return SegmentationResult(entries, "author_start", score)


# -------------------------------------------------------------- public --

def segment_references(lines: list[Line]) -> SegmentationResult:
    lines = [l for l in lines if l.text.strip()]
    if not lines:
        return SegmentationResult([], "none", 0.0, ["references section is empty"])
    candidates = [_try_numbered(lines), _try_hanging_indent(lines), _try_author_start(lines)]
    best = max(candidates, key=lambda r: r.score)
    if best.score < 0.35 or not best.entries:
        # last resort: one blob, surfaced as a failure — never silent
        raw, ital = _join_entry_lines(lines)
        return SegmentationResult(
            [RawEntry(None, raw, ital, lines)], "none", 0.0,
            ["Could not segment the reference list into entries; kept as one block."])
    best.notes.append(
        f"strategy={best.strategy} score={best.score:.2f} entries={len(best.entries)}")
    return best
