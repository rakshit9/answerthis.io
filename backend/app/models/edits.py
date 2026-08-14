"""Agentic-edit models: proposals, diffs, integrity reports.

Nothing mutates the paper directly. A natural-language command produces an
``EditProposal``; the user approves or rejects each section change; only
approved changes are applied (with a version snapshot for undo).
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .core import Reference


class ProposalStatus(str, Enum):
    RUNNING = "running"           # the agent is still working
    PROPOSED = "proposed"
    APPLIED = "applied"           # at least one change applied
    REJECTED = "rejected"
    FAILED = "failed"


class CitationAdd(BaseModel):
    ref_id: str
    reason: str                              # why the agent added it
    api: str                                 # provenance: which API it came from
    source_url: str                          # real link — required
    anchor_text: Optional[str] = None        # the sentence it was attached to


class CitationRemoval(BaseModel):
    """A citation the proposal would drop. NEVER silent: every removal is
    listed here and the UI requires explicit acknowledgement."""
    ref_id: str
    section_id: str
    reason: str


class IntegrityViolation(BaseModel):
    kind: str            # "citation_lost" | "unknown_ref" | "uncited_claim" | ...
    message: str
    section_id: Optional[str] = None
    ref_ids: list[str] = Field(default_factory=list)


class IntegrityReport(BaseModel):
    ok: bool = True
    checked_at: float = Field(default_factory=time.time)
    violations: list[IntegrityViolation] = Field(default_factory=list)   # blockers
    warnings: list[IntegrityViolation] = Field(default_factory=list)     # surfaced, non-blocking
    summary: str = ""


class SectionChange(BaseModel):
    id: str = Field(default_factory=lambda: "chg_" + uuid.uuid4().hex[:8])
    section_id: str
    section_title: str
    before: str                              # token-bearing text
    after: str
    rationale: str = ""
    citations_before: list[str] = Field(default_factory=list)   # ref-id multiset
    citations_after: list[str] = Field(default_factory=list)
    approved: Optional[bool] = None          # None = undecided


class AgentStep(BaseModel):
    """One entry in the agent's visible action log (plan → tool calls)."""
    t: float = Field(default_factory=time.time)
    kind: str                                # "plan" | "search" | "draft" | "check" | "error"
    text: str
    data: dict[str, Any] = Field(default_factory=dict)


class EditProposal(BaseModel):
    id: str = Field(default_factory=lambda: "prop_" + uuid.uuid4().hex[:10])
    paper_id: str
    command: str                             # the user's natural-language ask
    created_at: float = Field(default_factory=time.time)
    status: ProposalStatus = ProposalStatus.PROPOSED
    plan: str = ""                           # the agent's stated plan
    steps: list[AgentStep] = Field(default_factory=list)
    changes: list[SectionChange] = Field(default_factory=list)
    new_references: list[Reference] = Field(default_factory=list)
    citation_adds: list[CitationAdd] = Field(default_factory=list)
    citation_removals: list[CitationRemoval] = Field(default_factory=list)
    integrity: IntegrityReport = Field(default_factory=IntegrityReport)
    error: Optional[str] = None
    llm_used: Optional[str] = None
