"""Reference resolution: parsed reference → real external record.

Ladder (cheapest, most certain first):
  R1. DOI present    → OpenAlex by DOI, else Semantic Scholar by DOI
  R2. arXiv id       → Semantic Scholar by arXiv id
  R3. title parsed   → OpenAlex title search, then S2 keyword search;
                       candidates scored by title similarity (+ year and
                       first-author agreement); accept ≥ ACCEPT_SCORE.
  R4. otherwise      → honestly UNRESOLVED (never guessed)

A resolved reference keeps its identity (id, raw text, parse metadata) but
its canonical CSL-JSON is upgraded to the external record's CSL, and the
abstract is stored for claim checking. API failures mark the reference
FAILED with the error message — visible in the UI, never silent.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..models.core import Reference, Resolution, ResolutionStatus
from ..models.findings import ExternalSource
from .cache import ApiError
from . import openalex, semantic_scholar

ACCEPT_SCORE = 0.92
AMBIGUOUS_SCORE = 0.75


def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(norm_title(a), norm_title(b)) / 100.0


def score_candidate(ref: Reference, cand: ExternalSource) -> float:
    """0..1 — how confident are we that ``cand`` is the cited work?"""
    if not ref.parsed.title:
        return 0.0
    s = title_similarity(ref.parsed.title, cand.title)
    if ref.parsed.year and cand.year:
        if abs(ref.parsed.year - cand.year) > 2:
            s -= 0.15
        elif ref.parsed.year == cand.year:
            s += 0.03
    if ref.parsed.authors and cand.authors:
        fam = ref.parsed.authors[0].split(",")[0].strip().lower()
        first = cand.authors[0].lower()
        if fam and fam in first:
            s += 0.03
        elif fam and all(fam not in a.lower() for a in cand.authors[:5]):
            s -= 0.1
    return max(0.0, min(1.0, s))


def _apply(ref: Reference, src: ExternalSource, method: str, score: float) -> None:
    ref.resolution = Resolution(
        status=ResolutionStatus.RESOLVED,
        source=src.api, source_id=src.api_id, source_url=src.url,
        doi=src.doi, match_score=round(score, 3), method=method,
        abstract=src.abstract)
    csl = dict(src.csl)
    csl["id"] = ref.id                    # canonical id stays ours
    ref.csl = csl


def resolve_reference(ref: Reference) -> Reference:
    """Mutates and returns ``ref``. Never raises; failures land in
    ``ref.resolution.error``."""
    p = ref.parsed
    try:
        # ---- R1: DOI ---------------------------------------------------
        if p.doi:
            src = None
            try:
                src = openalex.by_doi(p.doi)
            except ApiError:
                src = None
            if src is None:
                try:
                    src = semantic_scholar.by_doi(p.doi)
                except ApiError:
                    src = None
            if src:
                _apply(ref, src, "doi", 1.0)
                return ref
        # ---- R2: arXiv -------------------------------------------------
        if p.arxiv_id:
            try:
                src = semantic_scholar.by_arxiv(p.arxiv_id)
            except ApiError:
                src = None
            if src:
                _apply(ref, src, "arxiv", 1.0)
                return ref
        # ---- R3: title search ------------------------------------------
        if p.title and len(p.title) >= 8:
            candidates: list[ExternalSource] = []
            errors: list[str] = []
            try:
                candidates += openalex.by_title(p.title)
            except ApiError as e:
                errors.append(str(e))
            best, best_score = _best(ref, candidates)
            if best is None or best_score < ACCEPT_SCORE:
                try:
                    candidates += semantic_scholar.search(p.title, limit=5)
                except ApiError as e:
                    errors.append(str(e))
                best, best_score = _best(ref, candidates)
            if best is not None and best_score >= ACCEPT_SCORE:
                _apply(ref, best, "title_search", best_score)
                return ref
            if best is not None and best_score >= AMBIGUOUS_SCORE:
                ref.resolution = Resolution(
                    status=ResolutionStatus.AMBIGUOUS,
                    source=best.api, source_id=best.api_id, source_url=best.url,
                    doi=best.doi, match_score=round(best_score, 3),
                    method="title_search",
                    error=("Best match below confidence threshold"
                           + ("; " + "; ".join(errors) if errors else "")))
                return ref
            ref.resolution = Resolution(
                status=ResolutionStatus.UNRESOLVED, method="title_search",
                error="; ".join(errors) if errors else
                "No plausible match on OpenAlex or Semantic Scholar")
            return ref
        # ---- R4 --------------------------------------------------------
        ref.resolution = Resolution(
            status=ResolutionStatus.UNRESOLVED,
            error="Not enough parsed fields (no DOI, arXiv id, or title)")
        return ref
    except Exception as e:                                    # noqa: BLE001
        ref.resolution = Resolution(status=ResolutionStatus.FAILED, error=str(e))
        return ref


def _best(ref: Reference, candidates: list[ExternalSource]
          ) -> tuple[ExternalSource | None, float]:
    best, best_score = None, 0.0
    for c in candidates:
        s = score_candidate(ref, c)
        if s > best_score:
            best, best_score = c, s
    return best, best_score
