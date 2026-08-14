"""Review orchestrator: runs a ReviewRun over a paper.

Order of operations:
  1. Introspective findings (free): unparsed references, unlinked markers.
  2. Reference resolution for cited refs (needed by claim checks; progress
     is streamed so the user sees the API boundary working — or failing).
  3. Claim–citation checks (sampled, capped).
  4. Missing-work search.
Findings are sorted by severity; the run log keeps every step honest.
"""
from __future__ import annotations

import time
import traceback

from ..config import settings
from ..llm.providers import build_provider
from ..models.core import PaperDocument, ResolutionStatus, SectionKind
from ..models.findings import Finding, FindingType, ReviewRun, ReviewStatus
from ..external.resolve import resolve_reference
from . import claims, missing

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def run_review(doc: PaperDocument, run: ReviewRun, save) -> None:
    """Mutates ``run`` in place; ``save()`` persists intermediate state so
    the UI can poll progress. Never raises."""

    def progress(msg: str) -> None:
        run.progress.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        save()

    llm = build_provider()
    scope = run.scope or {}
    do_missing = scope.get("missing_work", True)
    do_claims = scope.get("claim_checks", True)
    section_ids = set(scope["section_ids"]) if scope.get("section_ids") else None

    try:
        run.status = ReviewStatus.RUNNING
        progress(f"Review started (LLM: {llm.label if llm else 'none configured'})")

        # ---- 1. introspective findings --------------------------------
        for ref in doc.references:
            if ref.parse_confidence < 0.5:
                run.findings.append(Finding(
                    type=FindingType.UNPARSED_REFERENCE, severity="medium",
                    title=f"Reference {ref.label or ref.id} could not be parsed",
                    detail="Raw text kept: “" + ref.raw_text[:220] + "”. Issues: "
                           + "; ".join(ref.parse_issues or ["unknown"]),
                    ref_ids=[ref.id], provenance="parser confidence "
                    f"{ref.parse_confidence}"))
        if doc.parse_report.n_intext_unmatched:
            run.findings.append(Finding(
                type=FindingType.STYLE_NOTE, severity="low",
                title=f"{doc.parse_report.n_intext_unmatched} in-text marker(s) "
                      "could not be linked to a reference",
                detail="They were left untouched in the text; see the parse report."))

        # ---- 2. resolve cited references ------------------------------
        cited = set(doc.cited_ref_ids())
        to_resolve = [r for r in doc.references
                      if r.resolution.status == ResolutionStatus.NOT_ATTEMPTED]
        # cited ones first — claim checks need them
        to_resolve.sort(key=lambda r: (r.id not in cited, r.id))
        if to_resolve:
            progress(f"Resolving {len(to_resolve)} references against "
                     f"OpenAlex / Semantic Scholar…")
        n_res = n_fail = 0
        for i, ref in enumerate(to_resolve):
            resolve_reference(ref)
            st = ref.resolution.status
            n_res += st == ResolutionStatus.RESOLVED
            n_fail += st == ResolutionStatus.FAILED
            if (i + 1) % 5 == 0:
                progress(f"  …{i + 1}/{len(to_resolve)} resolved so far")
        if to_resolve:
            progress(f"Resolution done: {n_res} resolved, {n_fail} lookup failures, "
                     f"{len(to_resolve) - n_res - n_fail} not found/ambiguous")
        for ref in doc.references:
            if ref.resolution.status in (ResolutionStatus.UNRESOLVED, ResolutionStatus.FAILED) \
                    and ref.parse_confidence >= 0.5 and ref.id in cited:
                run.findings.append(Finding(
                    type=FindingType.UNRESOLVED_REFERENCE, severity="low",
                    title=f"Could not find “{(ref.parsed.title or ref.raw_text)[:70]}…” "
                          "on OpenAlex/Semantic Scholar",
                    detail=ref.resolution.error or "No confident match.",
                    ref_ids=[ref.id],
                    provenance=f"resolution: {ref.resolution.status.value}"))
        save()

        # ---- 3. claim checks ------------------------------------------
        if do_claims:
            sample = claims.pick_citations_to_check(
                doc, section_ids, scope.get("max_claim_checks",
                                            settings.max_claim_checks_per_review))
            progress(f"Claim–citation checks: {len(sample)} citation sites sampled")
            run.findings.extend(claims.check_claims(doc, llm, sample, progress))
            save()

        # ---- 4. missing work ------------------------------------------
        if do_missing:
            secs = [s for s in doc.sections
                    if (section_ids is None or s.id in section_ids)
                    and s.kind in (SectionKind.BODY, SectionKind.ABSTRACT)]
            run.findings.extend(missing.find_missing_work(
                doc, llm, secs, progress,
                max_queries=scope.get("max_queries", settings.max_queries_per_review)))
            save()

        run.findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))
        run.status = ReviewStatus.DONE
        run.finished_at = time.time()
        progress(f"Review finished: {len(run.findings)} findings")
    except Exception as e:                                    # noqa: BLE001
        run.status = ReviewStatus.FAILED
        run.error = f"{e}\n{traceback.format_exc()[-1500:]}"
        run.finished_at = time.time()
        progress(f"Review FAILED: {e}")
    finally:
        save()
