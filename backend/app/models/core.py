"""Core document + citation data model.

Design notes
============
The single canonical representation for *every* citation — parsed from the
PDF or fetched from Semantic Scholar / OpenAlex — is **CSL-JSON** (stored in
``Reference.csl``). Everything else (parse fields, resolution provenance,
confidence) is metadata *around* that canonical item, never a competing
format.

Section text is stored with **inline citation tokens** of the form::

    [[citep:ref_3]]        parenthetical citation of one work
    [[citep:ref_1,ref_7]]  a citation group, e.g. "[1, 7]" or "(A 2020; B 2021)"
    [[citet:ref_3]]        narrative citation ("Vaswani et al. (2017) showed…"
                           — the author name stays in prose, so author-year
                           styles must render the year only)

(The natbib-style names ``citep``/``citet`` are deliberate.)

Tokens are the source of truth for where citations live. Rendering for the
UI or for LaTeX export replaces tokens with citeproc-formatted labels in the
selected CSL style. Because edits (human or LLM) operate on token-bearing
text, the integrity checker can compare token multisets before/after any
edit and guarantee that no citation is ever dropped silently.
"""
from __future__ import annotations

import re
import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Citation tokens
# --------------------------------------------------------------------------

CITE_TOKEN_RE = re.compile(r"\[\[cite([pt]):([A-Za-z0-9_,\- ]+?)\]\]")


def make_cite_token(ref_ids: list[str], narrative: bool = False) -> str:
    kind = "t" if narrative else "p"
    return f"[[cite{kind}:" + ",".join(ref_ids) + "]]"


def extract_token_ref_ids(text: str) -> list[str]:
    """All reference ids mentioned by tokens in ``text``, in order, with
    duplicates preserved (it's a multiset for integrity checking)."""
    out: list[str] = []
    for m in CITE_TOKEN_RE.finditer(text):
        out.extend(r.strip() for r in m.group(2).split(",") if r.strip())
    return out


# --------------------------------------------------------------------------
# References (canonical: CSL-JSON)
# --------------------------------------------------------------------------

class ResolutionStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    RESOLVED = "resolved"          # confidently matched to an external record
    AMBIGUOUS = "ambiguous"        # candidates found, none confident enough
    UNRESOLVED = "unresolved"      # searched, nothing plausible found
    FAILED = "failed"              # the lookup itself failed (network, 429...)


class Resolution(BaseModel):
    status: ResolutionStatus = ResolutionStatus.NOT_ATTEMPTED
    source: Optional[str] = None          # "openalex" | "semantic_scholar"
    source_id: Optional[str] = None
    source_url: Optional[str] = None      # human-clickable link
    doi: Optional[str] = None
    match_score: Optional[float] = None   # 0..1 title-similarity based
    method: Optional[str] = None          # "doi" | "arxiv" | "title_search"
    error: Optional[str] = None           # honest failure message
    abstract: Optional[str] = None        # fetched abstract (for claim checks)


class ParsedFields(BaseModel):
    """Intermediate representation between the raw reference string and
    CSL-JSON: what our own parser extracted, before external resolution."""
    authors: list[str] = Field(default_factory=list)   # "Family, Given" strings
    year: Optional[int] = None
    title: Optional[str] = None
    container: Optional[str] = None       # journal / conference / book
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    pages: Optional[str] = None
    volume: Optional[str] = None


class Reference(BaseModel):
    id: str                                # "ref_1", "ref_2", ... stable
    raw_text: str                          # exactly as it appeared in the PDF
    label: Optional[str] = None            # list marker, e.g. "12" or "[12]"
    parsed: ParsedFields = Field(default_factory=ParsedFields)
    parse_confidence: float = 0.0          # 0..1 from the field parser
    parse_issues: list[str] = Field(default_factory=list)   # surfaced, not hidden
    csl: dict[str, Any] = Field(default_factory=dict)       # CANONICAL CSL-JSON
    resolution: Resolution = Field(default_factory=Resolution)
    added_by: str = "pdf_parse"            # "pdf_parse" | "agent" | "user"
    added_reason: Optional[str] = None     # provenance for agent-added refs

    @property
    def is_parsed(self) -> bool:
        return self.parse_confidence >= 0.5 and bool(self.parsed.title or self.parsed.authors)

    def best_url(self) -> Optional[str]:
        if self.resolution.source_url:
            return self.resolution.source_url
        doi = self.resolution.doi or self.parsed.doi or self.csl.get("DOI")
        if doi:
            return f"https://doi.org/{doi}"
        if self.parsed.arxiv_id:
            return f"https://arxiv.org/abs/{self.parsed.arxiv_id}"
        return self.parsed.url or self.csl.get("URL")


# --------------------------------------------------------------------------
# In-text citations (derived view; tokens in section text are ground truth)
# --------------------------------------------------------------------------

class InTextCitation(BaseModel):
    section_id: str
    raw: str                               # original surface form, e.g. "[1, 7]"
    ref_ids: list[str]                     # resolved reference ids
    unmatched: list[str] = Field(default_factory=list)  # marker parts we could not link
    context: str = ""                      # the sentence containing the marker


class IntextStyle(str, Enum):
    NUMERIC_BRACKET = "numeric_bracket"     # [1], [1,3-5]
    NUMERIC_SUPERSCRIPT = "superscript"     # word^1
    AUTHOR_YEAR = "author_year"             # (Smith et al., 2020) / Smith (2020)
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------
# Document structure
# --------------------------------------------------------------------------

class SectionKind(str, Enum):
    ABSTRACT = "abstract"
    BODY = "body"
    REFERENCES = "references"
    OTHER = "other"        # acknowledgements, appendix, footer matter


class Section(BaseModel):
    id: str
    title: str
    level: int = 1
    kind: SectionKind = SectionKind.BODY
    content: str = ""                      # token-bearing text
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class FloatKind(str, Enum):
    FIGURE = "figure"
    TABLE = "table"
    BOX = "box"            # bordered/filled panel (tcolorbox, framed defs, …)


class FloatBlock(BaseModel):
    """A figure, table, or boxed panel captured out of the prose flow.

    The parser cannot reconstruct visual layout from a PDF, so the honest
    contract is: the float's *text* is preserved here (never silently
    dropped) and excluded from section prose, where it would otherwise
    bleed into paragraphs as garbled inline text."""
    id: str
    kind: FloatKind
    caption: str = ""
    text: str = ""                         # extracted text, layout not preserved
    page: int                              # 0-based
    section_id: Optional[str] = None       # section whose prose surrounds it


class ParseWarning(BaseModel):
    stage: str                             # which pipeline stage raised it
    message: str
    detail: Optional[str] = None


class ParseReport(BaseModel):
    """Everything the user should see about how their PDF was parsed —
    including what failed. Nothing is dropped silently."""
    stages: list[str] = Field(default_factory=list)   # human-readable log
    warnings: list[ParseWarning] = Field(default_factory=list)
    n_pages: int = 0
    n_references_found: int = 0
    n_references_parsed: int = 0
    n_references_unparsed: int = 0
    n_intext_citations: int = 0
    n_intext_unmatched: int = 0
    n_floats: int = 0
    intext_style: IntextStyle = IntextStyle.UNKNOWN
    intext_style_confidence: float = 0.0


class PaperMeta(BaseModel):
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""


class DocumentVersion(BaseModel):
    version: int
    created_at: float
    reason: str                            # "initial parse" | edit description
    proposal_id: Optional[str] = None
    sections: list[Section]
    references: list[Reference]


class PaperDocument(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    filename: str = ""
    uploaded_at: float = Field(default_factory=time.time)
    meta: PaperMeta = Field(default_factory=PaperMeta)
    sections: list[Section] = Field(default_factory=list)
    floats: list[FloatBlock] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    intext_citations: list[InTextCitation] = Field(default_factory=list)
    parse_report: ParseReport = Field(default_factory=ParseReport)
    csl_style: str = "ieee"                # selected CSL style id
    csl_style_detected: bool = False
    version: int = 1
    history: list[DocumentVersion] = Field(default_factory=list)

    # ---- helpers ------------------------------------------------------
    def ref_by_id(self, ref_id: str) -> Optional[Reference]:
        for r in self.references:
            if r.id == ref_id:
                return r
        return None

    def section_by_id(self, section_id: str) -> Optional[Section]:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None

    def body_sections(self) -> list[Section]:
        return [s for s in self.sections if s.kind in (SectionKind.BODY, SectionKind.ABSTRACT)]

    def cited_ref_ids(self) -> list[str]:
        out: list[str] = []
        for s in self.sections:
            out.extend(extract_token_ref_ids(s.content))
        return out

    def snapshot(self, reason: str, proposal_id: str | None = None) -> None:
        """Push current state into history before mutating."""
        self.history.append(
            DocumentVersion(
                version=self.version,
                created_at=time.time(),
                reason=reason,
                proposal_id=proposal_id,
                sections=[s.model_copy(deep=True) for s in self.sections],
                references=[r.model_copy(deep=True) for r in self.references],
            )
        )
        self.version += 1
