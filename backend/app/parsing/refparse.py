"""Stage D: one raw reference string → structured fields → CSL-JSON.

Layered, deterministic extraction. Each layer removes what it matched so
later layers work on the remainder:

  D1. Identifiers: DOI, arXiv id, URL (unambiguous regexes).
  D2. Year: "(2015)" preferred (author-year styles), else a plausible
      standalone 19xx/20xx (numbered styles put it near the end).
  D3. Title/authors split, trying in order:
        a) quoted title  — "…," style (IEEE):  authors " TITLE " venue
        b) APA anchor    — authors "(2015)." title "." venue
        c) sentence split — authors "." title "." venue  (numbered styles
           without quotes), validated by name-likeness of the author chunk
      Italic segments from the PDF are used as a venue/title hint.
  D4. Author-list splitting into "Family, Given" pairs, handling
      "Family, F. M."-lists, "F. M. Family"-lists, "Family FM" (Vancouver),
      "and"/"&"/";" separators and a trailing "et al." marker.
  D5. Venue/volume/pages from the remainder.
  D6. Confidence score + explicit parse issues; below-threshold entries are
      surfaced to the user as unparsed, never dropped.

The output feeds ``to_csl`` which builds the canonical CSL-JSON item.
"""
from __future__ import annotations

import re

from ..models.core import ParsedFields

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
ARXIV_RE = re.compile(r"(?:arxiv[:\s/]*|abs/)(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
URL_RE = re.compile(r"https?://[^\s<>\)\]]+", re.I)
YEAR_PAREN_RE = re.compile(r"\((\d{4})([a-z])?\)")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})([a-z])?\b")
QUOTED_TITLE_RE = re.compile(r"[“\"]([^”\"]{8,300})[”\"]")
PAGES_RE = re.compile(r"\b(?:pp?\.\s*)(\d+\s*[–\-]\s*\d+)")
PAGES_COLON_RE = re.compile(r"\b\d+\s*\(\d+\)\s*:\s*(\d+\s*[–\-]\s*\d+)")
VOLUME_RE = re.compile(r"\b(?:vol\.?\s*)(\d+)", re.I)

_ET_AL_RE = re.compile(r",?\s*(?:et al\.?|and others)\s*$", re.I)
_NAME_PARTICLES = {"van", "von", "der", "de", "del", "da", "di", "la", "le",
                   "al", "bin", "ben", "ter", "ten"}


def _looks_like_names(chunk: str) -> bool:
    """Is this chunk plausibly an author list?"""
    chunk = chunk.strip().rstrip(".,")
    if not (3 <= len(chunk) <= 400):
        return False
    words = [w for w in re.split(r"[\s,]+", chunk) if w]
    if not words:
        return False
    caps = 0
    for w in words:
        wl = w.lower().strip(".&")
        if wl in _NAME_PARTICLES or wl in {"and", "et", "al", ""}:
            caps += 1
        elif w[0].isupper() or (len(w) <= 3 and w.rstrip(".").isupper()):
            caps += 1
    return caps / len(words) >= 0.8


def split_authors(s: str) -> tuple[list[str], list[str]]:
    """Author string → (["Family, Given", ...], issues)."""
    issues: list[str] = []
    s = _clean_author_part(s.strip().rstrip(";"))
    if not s:
        return [], ["no author text"]
    if _ET_AL_RE.search(s):
        s = _ET_AL_RE.sub("", s)
        issues.append("author list truncated with 'et al.'")

    # unify separators
    s = re.sub(r"\s*&\s*", " and ", s)
    s = re.sub(r",\s+and\s+", " and ", s)

    authors: list[str] = []

    if ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
    else:
        parts = _split_comma_run(s)

    for p in parts:
        p = _clean_author_part(p)
        if not p:
            continue
        authors.append(_normalize_name(p))

    if not authors:
        issues.append("could not split author names")
    return authors, issues


def _clean_author_part(p: str) -> str:
    """Trim separators but keep the final dot of initials ('Ba, J.')."""
    p = p.strip().strip(",").strip()
    if p.endswith(".") and not re.search(r"(?:^|[\s.])[A-Z]\.$", p):
        p = p[:-1]
    return p


_SURNAME_TOK = re.compile(r"(?:(?:van|von|der|de|del|da|di|la|le|ter|ten|al)\s+)*"
                          r"[A-Z][\w'’\-]+\.?")
_GIVEN_TOK = re.compile(r"[A-Z][\w'’\.\-]*(?:\s+[A-Z][\w'’\.\-]*){0,2}")


def _split_comma_run(s: str) -> list[str]:
    """Split a comma/'and'-separated author run into per-author strings.

    The hard case is telling  "Duchi, John, Hazan, Elad"  (Family, Given
    pairs) from  "Jimmy Lei Ba, Jamie Ryan Kiros"  (one author per token).
    Evidence used, in order:
      * the part after the final "and" contains a comma  → pair mode
      * an even number of single-word-ish tokens that alternate
        surname-like / given-like                         → pair mode
      * otherwise                                          → token mode
    """
    flat = re.sub(r"\s+and\s+", ", ", s)
    toks = [t.strip() for t in flat.split(",") if t.strip()]
    if not toks:
        return []

    pair_mode = False
    if " and " in s:
        tail = s.rsplit(" and ", 1)[1]
        if "," in tail:
            pair_mode = True
    if not pair_mode and len(toks) >= 2 and len(toks) % 2 == 0:
        surnames_ok = all(_SURNAME_TOK.fullmatch(t) for t in toks[0::2])
        givens_ok = all(_GIVEN_TOK.fullmatch(t) and len(t) <= 30 for t in toks[1::2])
        no_multi_surname = all(" " not in t or t.split()[0].islower() for t in toks[0::2])
        if surnames_ok and givens_ok and no_multi_surname:
            pair_mode = True

    if pair_mode and len(toks) % 2 == 0:
        return [f"{toks[i]}, {toks[i + 1]}" for i in range(0, len(toks), 2)]
    if pair_mode:  # odd count — fall back but keep obvious Family+initials pairs
        out, i = [], 0
        while i < len(toks):
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            if nxt and re.fullmatch(r"(?:[A-Z]\.?[\s\-]*)+", nxt):
                out.append(f"{toks[i]}, {nxt}")
                i += 2
            else:
                out.append(toks[i])
                i += 1
        return out
    return toks


def _normalize_name(name: str) -> str:
    """→ 'Family, Given' string."""
    name = re.sub(r"\s+", " ", name).strip()
    if "," in name:                      # already Family, Given
        fam, giv = name.split(",", 1)
        return f"{fam.strip()}, {giv.strip()}"
    words = name.split(" ")
    if len(words) == 1:
        return words[0]
    # "F. M. Family" or "Given Family" or "Family FM" (Vancouver)
    if re.fullmatch(r"[A-Z]{1,3}", words[-1]):          # Vancouver: Kingma DP
        fam = " ".join(words[:-1])
        giv = " ".join(f"{c}." for c in words[-1])
        return f"{fam}, {giv}"
    fam = words[-1]
    giv = " ".join(words[:-1])
    # keep particles with family name: "van der Maaten"
    parts = giv.split(" ")
    while parts and parts[-1].lower() in _NAME_PARTICLES:
        fam = parts.pop() + " " + fam
    return f"{fam}, {' '.join(parts)}".strip().rstrip(",")


def parse_entry(raw: str, italic_segments: list[str] | None = None
                ) -> tuple[ParsedFields, float, list[str]]:
    issues: list[str] = []
    fields = ParsedFields()
    rest = re.sub(r"\s+", " ", raw).strip()
    italic_segments = italic_segments or []

    # ---- D1 identifiers ----------------------------------------------
    if m := DOI_RE.search(rest):
        fields.doi = m.group(1).rstrip(".,;")
        rest = rest.replace(m.group(0), " ")
    if m := ARXIV_RE.search(rest):
        fields.arxiv_id = m.group(1)
    if m := URL_RE.search(rest):
        fields.url = m.group(0).rstrip(".,;")
        rest = rest.replace(m.group(0), " ")

    # ---- D2 year ------------------------------------------------------
    year_paren = None
    for m in YEAR_PAREN_RE.finditer(rest):
        if 1900 <= int(m.group(1)) <= 2035:
            year_paren = m
            break
    if year_paren:
        fields.year = int(year_paren.group(1))
    else:
        years = [int(m.group(1)) for m in YEAR_RE.finditer(rest)
                 if 1900 <= int(m.group(1)) <= 2035]
        if years:
            fields.year = years[-1]          # numbered styles: year at the end
    if fields.year is None:
        issues.append("no publication year found")

    # ---- D3 authors / title / venue split -----------------------------
    authors_chunk = title = venue = None

    if m := QUOTED_TITLE_RE.search(rest):                       # (a) IEEE quotes
        title = m.group(1).strip().rstrip(",.")
        authors_chunk = rest[:m.start()].strip().rstrip(",")
        venue = rest[m.end():].strip()
    elif year_paren:                                            # (b) APA anchor
        authors_chunk = rest[:year_paren.start()].strip().rstrip(",.")
        after = rest[year_paren.end():].lstrip(" .")
        title, venue = _split_first_sentence(after)
    else:                                                       # (c) sentence split
        chunks = _sentence_chunks(rest)
        if len(chunks) >= 2 and _looks_like_names(chunks[0]):
            authors_chunk = chunks[0]
            title = chunks[1].strip().rstrip(",.")
            venue = " ".join(chunks[2:]).strip()
        elif len(chunks) >= 2:
            # maybe title-first (rare) — flag it
            issues.append("could not confidently locate the author list")
            title = chunks[0].strip()
            venue = " ".join(chunks[1:]).strip()
        else:
            issues.append("entry has no recognizable sentence structure")

    # italic hints: an italic segment matching the tail is the venue;
    # matching the title slot for books means the italic IS the title.
    if venue is None and italic_segments:
        venue = italic_segments[-1]
    if title and italic_segments and not venue:
        pass

    if authors_chunk:
        fields.authors, a_issues = split_authors(authors_chunk)
        issues.extend(a_issues)
    else:
        issues.append("no author text")

    if title:
        fields.title = title.strip().rstrip(".,;")
    else:
        issues.append("no title found")

    # ---- D5 venue / volume / pages ------------------------------------
    if venue:
        v = venue
        if m := PAGES_RE.search(v):
            fields.pages = re.sub(r"\s", "", m.group(1))
        elif m := PAGES_COLON_RE.search(v):
            fields.pages = re.sub(r"\s", "", m.group(1))
        if m := VOLUME_RE.search(v):
            fields.volume = m.group(1)
        v = re.sub(r"^(In:?\s+|Proc\.?\s+of\s+)", "", v, flags=re.I)
        v = YEAR_RE.sub("", v)
        v = PAGES_RE.sub("", v)
        v = re.sub(r"\b(pp?\.|pages)\s*", "", v)
        v = re.sub(r"[,\.;:]\s*[,\.;:]", ",", v)
        v = v.strip(" ,.;:-–")
        # first solid chunk of the remainder is the container name
        vparts = [p.strip() for p in re.split(r"[,.](?:\s|$)", v) if len(p.strip()) > 3]
        if vparts:
            fields.container = vparts[0][:180]

    # ---- D6 confidence ------------------------------------------------
    conf = 0.0
    conf += 0.30 if fields.authors else 0.0
    conf += 0.30 if fields.title and len(fields.title) >= 8 else 0.0
    conf += 0.20 if fields.year else 0.0
    conf += 0.10 if fields.container else 0.0
    conf += 0.10 if (fields.doi or fields.arxiv_id or fields.url) else 0.0
    return fields, round(conf, 2), issues


_INITIALS_TOK = re.compile(r"[A-Z]\.(?:[A-Z]\.)*,?")
_NONBOUND_TOK = re.compile(r"Jr\.|Sr\.|St\.|Proc\.|Conf\.|Int\.|vol\.|pp\.|no\.|Vol\.|"
                           r"eds?\.|Univ\.|Dept\.|approx\.|resp\.|e\.g\.|i\.e\.|cf\.")


def _sentence_chunks(s: str) -> list[str]:
    """Split a reference entry on '. ' boundaries.

    Initials ("D. P. Kingma") normally do NOT end a chunk — except when the
    text accumulated so far already reads as a complete author list and the
    next word starts a new capitalized phrase ("…Salakhutdinov, R.R.
    Reducing the …"), which is exactly how author-first styles attach the
    title. "et al." ends the author chunk the same way.
    """
    out, buf = [], []
    tokens = s.split(" ")
    for i, tok in enumerate(tokens):
        buf.append(tok)
        if not tok.endswith("."):
            continue
        if _NONBOUND_TOK.fullmatch(tok):
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        nxt2 = tokens[i + 2] if i + 2 < len(tokens) else None
        if _INITIALS_TOK.fullmatch(tok) or tok == "al.":
            buf_text = " ".join(buf)
            has_surname = any(len(re.sub(r"[^A-Za-z]", "", t)) >= 3 for t in buf)
            names_done = (_looks_like_names(buf_text.rstrip(".").replace(" al", " al."))
                          if tok == "al." else _looks_like_names(buf_text))
            # The next word must start a new phrase (the title). A dotted
            # capitalized word ("Le.", "Smith.") is the *surname* finishing
            # the author list — the boundary will fire on it instead.
            nxt_letters = len(re.sub(r"[^A-Za-z]", "", nxt)) if nxt else 0
            starts_phrase = (nxt is not None and nxt[:1].isupper()
                             and not _INITIALS_TOK.fullmatch(nxt)
                             and not nxt.endswith(".")
                             and (nxt_letters >= 2
                                  or (nxt2 or "")[:1].islower()))
            if not (has_surname and names_done and starts_phrase):
                continue
        out.append(" ".join(buf))
        buf = []
    if buf:
        out.append(" ".join(buf))
    return [c.strip() for c in out if c.strip()]


def _split_first_sentence(s: str) -> tuple[str | None, str | None]:
    chunks = _sentence_chunks(s)
    if not chunks:
        return None, None
    title = chunks[0].strip().rstrip(".,")
    venue = " ".join(chunks[1:]).strip() or None
    return title, venue


# --------------------------------------------------------------------------
# CSL-JSON construction (canonical model)
# --------------------------------------------------------------------------

_CONF_WORDS = re.compile(r"proceedings|conference|workshop|symposium|meeting|"
                         r"\bicml\b|\bneurips\b|\bnips\b|\biclr\b|\bacl\b|\bcvpr\b|\biccv\b",
                         re.I)
_PREPRINT_WORDS = re.compile(r"arxiv|corr|preprint|biorxiv|ssrn", re.I)


def guess_csl_type(fields: ParsedFields) -> str:
    c = fields.container or ""
    if fields.arxiv_id or _PREPRINT_WORDS.search(c):
        return "article"                    # CSL type for preprints
    if _CONF_WORDS.search(c):
        return "paper-conference"
    if c:
        return "article-journal"
    return "article"


def to_csl(fields: ParsedFields, ref_id: str, raw_text: str = "") -> dict:
    """ParsedFields → canonical CSL-JSON item."""
    item: dict = {"id": ref_id, "type": guess_csl_type(fields)}
    if fields.title:
        item["title"] = fields.title
    authors = []
    for a in fields.authors:
        if "," in a:
            fam, giv = a.split(",", 1)
            authors.append({"family": fam.strip(), "given": giv.strip()})
        elif a:
            authors.append({"family": a})
    if authors:
        item["author"] = authors
    if fields.year:
        item["issued"] = {"date-parts": [[fields.year]]}
    if fields.container:
        item["container-title"] = fields.container
    if fields.doi:
        item["DOI"] = fields.doi
    if fields.url:
        item["URL"] = fields.url
    elif fields.arxiv_id:
        item["URL"] = f"https://arxiv.org/abs/{fields.arxiv_id}"
    if fields.pages:
        item["page"] = fields.pages
    if fields.volume:
        item["volume"] = fields.volume
    if fields.arxiv_id:
        item["note"] = f"arXiv:{fields.arxiv_id}"
    if raw_text and "title" not in item:
        item["note"] = (item.get("note", "") + f" | unparsed raw: {raw_text[:200]}").strip(" |")
    return item
