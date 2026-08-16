"""Small text utilities: sentence segmentation that survives academic prose
(initials, "et al.", "Fig.", "Eq.", inline citation tokens)."""
from __future__ import annotations

import re

# Python's ``re`` has no ``\p{Lu}``, and a literal ``[A-Z]`` silently excludes
# Müller, Álvarez, Öztürk, Nguyễn — surnames that are everywhere in real
# reference lists. Build the uppercase class once from the Latin-1 Supplement,
# Latin Extended-A/B, Greek and Cyrillic blocks (U+00C0–U+04FF); ``isupper()``
# is true only for Lu/Lt, so this is exact rather than a hand-guessed range.
UPPER_CLASS = "[A-Z" + re.escape(
    "".join(chr(c) for c in range(0xC0, 0x500) if chr(c).isupper())) + "]"

#: A capitalised word: uppercase initial + the usual name-internal characters.
NAME_WORD = UPPER_CLASS + r"[\w'’\-]*"

_ABBREV = (r"et al|e\.g|i\.e|cf|vs|Fig|Figs|Eq|Eqs|Sec|Secs|Tab|Ref|Refs|"
           r"Dr|Prof|Mr|Ms|Mrs|St|no|No|vol|Vol|pp|approx|resp")
_ABBREV_RE = re.compile(r"\b(?:" + _ABBREV + r")\.$")
_SENT_END_RE = re.compile(r"([.!?])(\s+)(?=[A-Z\[\(\d“\"'])")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character spans of sentences in ``text``."""
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENT_END_RE.finditer(text):
        end = m.end(1)
        prefix = text[start:end]
        tail = prefix[-14:]
        if _ABBREV_RE.search(tail.strip()):
            continue                      # "et al." etc. — not a boundary
        if re.search(r"\b[A-Z]\.$", prefix.strip()):
            continue                      # initials: "D. P. Kingma"
        spans.append((start, end))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def sentence_at(text: str, pos: int) -> str:
    for s, e in sentence_spans(text):
        if s <= pos < e:
            return text[s:e].strip()
    return text[max(0, pos - 120):pos + 120].strip()
