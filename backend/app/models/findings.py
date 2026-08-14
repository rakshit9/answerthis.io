"""Peer-review findings.

Hard rule encoded here: any finding that points at external work must carry
a real, clickable source URL and the provenance of how we found it (which
API, which query). A finding with no source is only allowed for
introspective types (e.g. "this reference could not be parsed").
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FindingType(str, Enum):
    MISSING_WORK = "missing_work"            # relevant paper not cited
    CLAIM_MISMATCH = "claim_mismatch"        # cited source doesn't support claim
    CLAIM_SUPPORTED = "claim_supported"      # positive check result (shown too)
    CLAIM_UNVERIFIABLE = "claim_unverifiable"  # no abstract / unresolved ref
    UNPARSED_REFERENCE = "unparsed_reference"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    SEARCH_FAILURE = "search_failure"        # honest "the lookup failed"
    STYLE_NOTE = "style_note"


class Verdict(str, Enum):
    SUPPORTS = "supports"
    PARTIAL = "partial"
    DOES_NOT_SUPPORT = "does_not_support"
    CANNOT_VERIFY = "cannot_verify"


class ExternalSource(BaseModel):
    """A real, linkable external work. Never fabricated: constructed only
    from OpenAlex / Semantic Scholar API responses."""
    api: str                                  # "openalex" | "semantic_scholar"
    api_id: str
    title: str
    year: Optional[int] = None
    authors: list[str] = Field(default_factory=list)
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: str                                  # ALWAYS present and clickable
    abstract: Optional[str] = None
    cited_by_count: Optional[int] = None
    csl: dict[str, Any] = Field(default_factory=dict)   # canonical CSL-JSON


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: "f_" + uuid.uuid4().hex[:10])
    created_at: float = Field(default_factory=time.time)
    type: FindingType
    severity: str = "info"                    # "high" | "medium" | "low" | "info"
    title: str
    detail: str = ""
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    claim_text: Optional[str] = None          # exact sentence being examined
    ref_ids: list[str] = Field(default_factory=list)
    verdict: Optional[Verdict] = None
    verdict_rationale: Optional[str] = None
    evidence_quote: Optional[str] = None      # sentence from the abstract
    source: Optional[ExternalSource] = None   # the linkable external work
    provenance: Optional[str] = None          # e.g. 'openalex search: "..."'
    confidence: Optional[float] = None
    llm_used: Optional[str] = None            # model that judged, if any


class ReviewStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ReviewRun(BaseModel):
    id: str = Field(default_factory=lambda: "rev_" + uuid.uuid4().hex[:10])
    paper_id: str
    started_at: float = Field(default_factory=time.time)
    finished_at: Optional[float] = None
    status: ReviewStatus = ReviewStatus.PENDING
    scope: dict[str, Any] = Field(default_factory=dict)   # what the user asked
    progress: list[str] = Field(default_factory=list)     # live log lines
    findings: list[Finding] = Field(default_factory=list)
    error: Optional[str] = None
