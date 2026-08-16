"""Stage E: locate in-text citation markers, link them to references, and
replace them with canonical ``[[citep:…]]`` / ``[[citet:…]]`` tokens.

Handles five marker families:

  E1. Numeric brackets  — "[3]", "[1, 4–7]" … linked via reference labels.
  E2. Superscript runs  — word⟨sup:12,13⟩ sentinels injected by stage B;
      only trusted when ≥3 distinct numbers map to reference labels AND the
      bracket style is absent (guards against footnote markers).
  E3. Author–year       — parenthetical "(Kingma & Ba, 2015; Smith 2020a)"
      and narrative "Vaswani et al. (2017)", linked by first-author family
      name (exact or fuzzy) + year, with a/b disambiguation.
  E4. Parenthesised numeric — "(1)", "(1, 3)" (PNAS, ACS, AMA). Shares the
      ambiguity problem of superscripts — "(3)" is also how equations are
      referenced — so it needs ≥3 linking numbers and the absence of the
      bracket style before it is trusted.
  E5. Bracketed author–year — "[Smith et al. 2020]" (ACM, humanities). Same
      linking logic as E3, different delimiters; pure-numeric brackets stay
      with E1.

Surname matching is Unicode-aware throughout: "[A-Z]" in Python is ASCII-only
and would drop Müller, Álvarez and Öztürk on the floor.

Anything that *looks* like a marker but cannot be linked is left verbatim
in the text and recorded as unmatched — surfaced, never silently dropped.

Output: tokenized section text + ``InTextCitation`` records + detected
style with confidence.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ..models.core import InTextCitation, IntextStyle, Reference, make_cite_token
from .structure import SUP_CLOSE, SUP_OPEN
from .textutil import NAME_WORD, sentence_at

_NUM_GROUP_RE = re.compile(r"\[(\d{1,3}(?:\s*[,;–\-]\s*\d{1,3})*)\]")
_SUP_RE = re.compile(re.escape(SUP_OPEN) + r"([\d,\s\-–]+)" + re.escape(SUP_CLOSE))
_PAREN_RE = re.compile(r"\(([^()]{2,300}?)\)")
# E4: parenthesised numeric markers — "(1)", "(1, 3)", "(1–4)" (PNAS, ACS, AMA).
# Deliberately the same shape as _NUM_GROUP_RE but round-bracketed; it collides
# with equation references ("as shown in (3)"), so it is only ever used behind
# the evidence guard in ``tokenize_sections``.
_PAREN_NUM_RE = re.compile(r"\((\d{1,3}(?:\s*[,;–\-]\s*\d{1,3})*)\)")
# E5: bracketed author–year — "[Smith et al. 2020]", "[Smith and Doe 2020]"
# (ACM, and much of the humanities). Inner text must contain a letter, so pure
# numeric groups stay with _NUM_GROUP_RE.
_BRACKET_AY_RE = re.compile(r"\[([^\[\]]{2,300}?)\]")
_YEARISH = re.compile(r"\b(19|20)\d{2}[a-z]?\b")
_NARRATIVE_RE = re.compile(
    r"\b(" + NAME_WORD + r")"                                # first surname
    r"(\s+(?:and|&)\s+" + NAME_WORD + r"|\s+et\s+al\.?)?"    # "and X" | "et al."
    r"\s*\((\d{4})([a-z])?\)")
#: one "Surname[ et al.|and Other][,] YEAR[a]" citation inside a group
_AY_PART_RE = re.compile(
    r"(" + NAME_WORD + r")(?:\s+(?:and|&)\s+" + NAME_WORD + r"|\s+et\s+al\.?|,)?"
    r"[\s,]*((?:19|20)\d{2})([a-z])?")
_CITE_PREFIX_RE = re.compile(r"^(?:see|e\.g\.|i\.e\.|cf\.|see,? e\.g\.,?|also|as in)[\s,]+", re.I)


@dataclass
class IntextResult:
    sections_tokenized: dict[str, str]          # section_id -> new content
    citations: list[InTextCitation] = field(default_factory=list)
    unmatched: list[dict] = field(default_factory=list)
    style: IntextStyle = IntextStyle.UNKNOWN
    style_confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- linking --

def _label_map(references: list[Reference]) -> dict[str, str]:
    return {r.label: r.id for r in references if r.label}


def _author_year_index(references: list[Reference]) -> dict[tuple[str, int], list[Reference]]:
    idx: dict[tuple[str, int], list[Reference]] = {}
    for r in references:
        if not r.parsed.authors or not r.parsed.year:
            continue
        fam = r.parsed.authors[0].split(",")[0].strip().lower()
        idx.setdefault((fam, r.parsed.year), []).append(r)
    return idx


def _match_author_year(surname: str, year: int, letter: str | None,
                       ay_index: dict[tuple[str, int], list[Reference]]) -> Reference | None:
    key = (surname.lower(), year)
    cands = ay_index.get(key)
    if not cands:
        # fuzzy surname (diacritics, hyphenation)
        best, best_score = None, 0.0
        for (fam, y), refs in ay_index.items():
            if y != year:
                continue
            score = fuzz.ratio(fam, surname.lower())
            if score > 88 and score > best_score:
                best, best_score = refs, score
        cands = best
    if not cands:
        return None
    if letter:
        i = ord(letter) - ord("a")
        return cands[i] if i < len(cands) else cands[0]
    return cands[0]


def _expand_numbers(group: str) -> list[int] | None:
    nums: list[int] = []
    for part in re.split(r"[,;]", group):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d{1,3})\s*[–\-]\s*(\d{1,3})", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b < a or b - a > 40:
                return None
            nums.extend(range(a, b + 1))
        elif part.isdigit():
            nums.append(int(part))
        else:
            return None
    return nums or None


# ------------------------------------------------------------- tokenizers --

def _tokenize_numeric(text: str, labels: dict[str, str], out: "IntextResult",
                      section_id: str) -> tuple[str, int]:
    hits = 0

    def repl(m: re.Match) -> str:
        nonlocal hits
        nums = _expand_numbers(m.group(1))
        if not nums:
            return m.group(0)
        ids = [labels.get(str(n)) for n in nums]
        if any(i is None for i in ids):
            missing = [str(n) for n, i in zip(nums, ids) if i is None]
            out.unmatched.append({"section_id": section_id, "raw": m.group(0),
                                  "reason": f"no reference numbered {', '.join(missing)}"})
            return m.group(0)               # leave the original text alone
        hits += 1
        out.citations.append(InTextCitation(
            section_id=section_id, raw=m.group(0), ref_ids=[i for i in ids if i],
            context=sentence_at(text, m.start())))
        return make_cite_token([i for i in ids if i])

    return _NUM_GROUP_RE.sub(repl, text), hits


def _tokenize_superscript(text: str, labels: dict[str, str], out: "IntextResult",
                          section_id: str) -> tuple[str, int]:
    hits = 0

    def repl(m: re.Match) -> str:
        nonlocal hits
        nums = _expand_numbers(m.group(1))
        if not nums:
            return ""
        ids = [labels.get(str(n)) for n in nums]
        if any(i is None for i in ids):
            out.unmatched.append({"section_id": section_id, "raw": m.group(0),
                                  "reason": "superscript numbers don't match reference labels"})
            return ""
        hits += 1
        out.citations.append(InTextCitation(
            section_id=section_id, raw="^" + m.group(1), ref_ids=[i for i in ids if i],
            context=sentence_at(text, m.start())))
        return make_cite_token([i for i in ids if i])

    return _SUP_RE.sub(repl, text), hits


def _strip_superscript_sentinels(text: str) -> str:
    return _SUP_RE.sub("", text)


def _parse_ay_group(inner: str, ay_index) -> list[str] | None:
    """"Kingma & Ba, 2015; Duchi et al., 2011" → [ref ids], or None if *any*
    part fails to link. All-or-nothing on purpose: a half-linked group would
    silently drop a citation, so the whole marker is left verbatim instead."""
    if not _YEARISH.search(inner):
        return None
    ids: list[str] = []
    for part in (p.strip() for p in inner.split(";")):
        if not part:
            continue
        pm = _AY_PART_RE.search(_CITE_PREFIX_RE.sub("", part))
        if not pm:
            return None
        ref = _match_author_year(pm.group(1), int(pm.group(2)), pm.group(3), ay_index)
        if ref is None:
            return None
        ids.append(ref.id)
    return ids or None


def _tokenize_paren_numeric(text: str, labels: dict[str, str], out: "IntextResult",
                            section_id: str) -> tuple[str, int]:
    """E4 — "(1)", "(1, 3)". Only called when the evidence guard has already
    established that this document really cites this way."""
    hits = 0

    def repl(m: re.Match) -> str:
        nonlocal hits
        nums = _expand_numbers(m.group(1))
        if not nums:
            return m.group(0)
        ids = [labels.get(str(n)) for n in nums]
        if any(i is None for i in ids):
            # Unlike E1 this is *expected* — "(3)" is very often an equation
            # reference, so it is left alone and not reported as a failure.
            return m.group(0)
        hits += 1
        out.citations.append(InTextCitation(
            section_id=section_id, raw=m.group(0), ref_ids=[i for i in ids if i],
            context=sentence_at(text, m.start())))
        return make_cite_token([i for i in ids if i])

    return _PAREN_NUM_RE.sub(repl, text), hits


def _tokenize_author_year(text: str, ay_index, out: "IntextResult",
                          section_id: str) -> tuple[str, int]:
    hits = 0

    # narrative first: "Vaswani et al. (2017)" → keep name, token the year
    def repl_narr(m: re.Match) -> str:
        nonlocal hits
        surname, _rest, year, letter = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        ref = _match_author_year(surname, year, letter, ay_index)
        if ref is None:
            return m.group(0)
        hits += 1
        name_part = m.group(0)[: m.group(0).rfind("(")].rstrip()
        out.citations.append(InTextCitation(
            section_id=section_id, raw=m.group(0), ref_ids=[ref.id],
            context=sentence_at(text, m.start())))
        return f"{name_part} {make_cite_token([ref.id], narrative=True)}"

    text = _NARRATIVE_RE.sub(repl_narr, text)

    # grouped markers, parenthesised "(Kingma & Ba, 2015; Duchi et al., 2011)"
    # and bracketed "[Kingma and Ba 2015]" — same logic, different delimiters
    def _repl_group(m: re.Match) -> str:
        nonlocal hits
        inner = m.group(1)
        ids = _parse_ay_group(inner, ay_index)
        if not ids:
            if _YEARISH.search(inner) and re.search(NAME_WORD, inner):
                out.unmatched.append({"section_id": section_id, "raw": m.group(0),
                                      "reason": "author–year marker didn't match any reference"})
            return m.group(0)
        hits += 1
        out.citations.append(InTextCitation(
            section_id=section_id, raw=m.group(0), ref_ids=ids,
            context=sentence_at(text, m.start())))
        return make_cite_token(ids)

    text = _PAREN_RE.sub(_repl_group, text)

    def _repl_bracket(m: re.Match) -> str:
        # pure-numeric brackets belong to E1 — never steal them here
        if not re.search(r"[^\W\d_]", m.group(1)):
            return m.group(0)
        return _repl_group(m)

    text = _BRACKET_AY_RE.sub(_repl_bracket, text)
    return text, hits


# ------------------------------------------------------------------ main --

def tokenize_sections(section_texts: dict[str, str], references: list[Reference]
                      ) -> IntextResult:
    """``section_texts``: section_id → flattened text (with ⟨sup:⟩ sentinels)."""
    out = IntextResult(sections_tokenized={})
    labels = _label_map(references)
    ay_index = _author_year_index(references)

    # ---- probe pass: which family of markers actually links? ----------
    probe_counts: Counter[str] = Counter()
    for text in section_texts.values():
        for m in _NUM_GROUP_RE.finditer(text):
            nums = _expand_numbers(m.group(1))
            if nums and all(str(n) in labels for n in nums):
                probe_counts["numeric"] += 1
        for m in _SUP_RE.finditer(text):
            nums = _expand_numbers(m.group(1))
            if nums and all(str(n) in labels for n in nums):
                probe_counts["superscript"] += 1
        for m in _NARRATIVE_RE.finditer(text):
            if _match_author_year(m.group(1), int(m.group(3)), m.group(4), ay_index):
                probe_counts["author_year"] += 1
        for m in _PAREN_RE.finditer(text):
            if _parse_ay_group(m.group(1), ay_index):
                probe_counts["author_year"] += 1
        for m in _BRACKET_AY_RE.finditer(text):
            if re.search(r"[^\W\d_]", m.group(1)) and _parse_ay_group(m.group(1), ay_index):
                probe_counts["author_year"] += 1
        for m in _PAREN_NUM_RE.finditer(text):
            nums = _expand_numbers(m.group(1))
            if nums and all(str(n) in labels for n in nums):
                probe_counts["paren_numeric"] += 1

    total = sum(probe_counts.values())
    dominant, dom_count = (probe_counts.most_common(1)[0] if probe_counts else ("none", 0))

    style = IntextStyle.UNKNOWN
    conf = 0.0
    if total:
        conf = dom_count / total
        style = {"numeric": IntextStyle.NUMERIC_BRACKET,
                 "superscript": IntextStyle.NUMERIC_SUPERSCRIPT,
                 "paren_numeric": IntextStyle.NUMERIC_PAREN,
                 "author_year": IntextStyle.AUTHOR_YEAR}.get(dominant, IntextStyle.UNKNOWN)

    # superscript guard: needs ≥3 distinct linked numbers to beat "footnotes"
    use_superscript = (style == IntextStyle.NUMERIC_SUPERSCRIPT and dom_count >= 3)
    # paren-numeric guard: same reasoning against equation references, plus the
    # bracket style must be absent — a paper doing both is doing "[1]" and
    # numbering its equations, not citing as "(1)".
    use_paren_numeric = (style == IntextStyle.NUMERIC_PAREN and dom_count >= 3
                         and not probe_counts["numeric"])
    if style == IntextStyle.NUMERIC_PAREN and not use_paren_numeric:
        out.notes.append(
            f"Saw {dom_count} parenthesised numeric marker(s) like '(1)', but not enough "
            f"evidence to treat them as citations rather than equation references; "
            f"they were left as plain text.")
        style, conf = IntextStyle.UNKNOWN, 0.0

    # ---- tokenize pass ------------------------------------------------
    for sid, text in section_texts.items():
        if style == IntextStyle.NUMERIC_BRACKET:
            text, _ = _tokenize_numeric(text, labels, out, sid)
            text = _strip_superscript_sentinels(text)
        elif use_superscript:
            text, _ = _tokenize_superscript(text, labels, out, sid)
        elif use_paren_numeric:
            text, _ = _tokenize_paren_numeric(text, labels, out, sid)
            text = _strip_superscript_sentinels(text)
        elif style == IntextStyle.AUTHOR_YEAR:
            text = _strip_superscript_sentinels(text)
            text, _ = _tokenize_author_year(text, ay_index, out, sid)
        else:
            # unknown: try numeric then author-year, honest about ambiguity
            text, n1 = _tokenize_numeric(text, labels, out, sid)
            text = _strip_superscript_sentinels(text)
            text, n2 = _tokenize_author_year(text, ay_index, out, sid)
            if n1 or n2:
                out.notes.append(f"section {sid}: mixed/unknown style "
                                 f"(numeric={n1}, author-year={n2})")
        out.sections_tokenized[sid] = text

    out.style = style
    out.style_confidence = round(conf, 2)
    if total == 0:
        out.notes.append("No in-text citation markers could be linked to references.")
    return out
