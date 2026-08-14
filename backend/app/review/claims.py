"""Claim–citation matching: does the cited source actually support the
sentence it is attached to?

Per sampled in-text citation:
  K1. The claim = the sentence containing the citation marker (extracted at
      parse time, tokens stripped for readability).
  K2. Evidence = the cited work's abstract, fetched during reference
      resolution from OpenAlex / Semantic Scholar. No abstract → the check
      honestly returns CLAIM_UNVERIFIABLE instead of guessing.
  K3. Judgment = an LLM verdict (supports / partial / does_not_support /
      cannot_verify) grounded ONLY in that abstract, temperature 0. The
      returned evidence quote is verified verbatim-ish against the abstract
      (fuzzy ≥ 85) — a fabricated quote is discarded and the finding says so.
  K4. No LLM configured → every check is CLAIM_UNVERIFIABLE, stated openly.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..external.resolve import resolve_reference
from ..llm.base import LLMError, LLMProvider
from ..models.core import CITE_TOKEN_RE, InTextCitation, PaperDocument, ResolutionStatus
from ..models.findings import ExternalSource, Finding, FindingType, Verdict

_JUDGE_SYSTEM = """You are a careful peer reviewer checking one citation.
Given a CLAIM from a manuscript and the ABSTRACT of the work it cites, judge
whether the cited work supports the claim as used.

Return JSON:
{"verdict": "supports" | "partial" | "does_not_support" | "cannot_verify",
 "rationale": "<one or two sentences>",
 "quote": "<a verbatim sentence from the abstract that best justifies your verdict, or null>",
 "confidence": 0.0-1.0}

Rules:
- Judge ONLY from the abstract text given. If the abstract is about the right
  work but doesn't contain enough information to judge the specific claim,
  use "cannot_verify" — do not assume.
- "partial" = the source is topically right but the claim overstates,
  misattributes, or adds specifics the abstract doesn't back.
- The quote must be copied verbatim from the abstract. Never invent one."""


def _clean_claim(citation: InTextCitation) -> str:
    text = CITE_TOKEN_RE.sub("", citation.context)
    return re.sub(r"\s+", " ", text).strip()


def pick_citations_to_check(doc: PaperDocument, section_ids: set[str] | None,
                            max_checks: int) -> list[InTextCitation]:
    """Spread checks across sections and distinct references; prefer
    assertive sentences (long enough to contain an actual claim)."""
    pool = [c for c in doc.intext_citations
            if (section_ids is None or c.section_id in section_ids)
            and len(_clean_claim(c)) >= 25]
    seen_refs: set[str] = set()
    first_pass, second_pass = [], []
    for c in pool:
        key = tuple(sorted(c.ref_ids))
        if any(r not in seen_refs for r in c.ref_ids):
            first_pass.append(c)
            seen_refs.update(c.ref_ids)
        else:
            second_pass.append(c)
        _ = key
    return (first_pass + second_pass)[:max_checks]


def check_claims(doc: PaperDocument, llm: LLMProvider | None,
                 citations: list[InTextCitation], progress) -> list[Finding]:
    findings: list[Finding] = []
    for cit in citations:
        claim = _clean_claim(cit)
        section = doc.section_by_id(cit.section_id)
        for ref_id in cit.ref_ids:
            ref = doc.ref_by_id(ref_id)
            if ref is None:
                continue
            # ---- K2: make sure we have an abstract ---------------------
            if ref.resolution.status == ResolutionStatus.NOT_ATTEMPTED:
                progress(f"Resolving {ref_id} for claim check…")
                resolve_reference(ref)
            src_url = ref.best_url()
            source = _source_from_ref(ref)
            if not ref.resolution.abstract:
                reason = {
                    ResolutionStatus.RESOLVED: "the source record has no abstract",
                    ResolutionStatus.AMBIGUOUS: "the reference could not be confidently matched to an external record",
                    ResolutionStatus.UNRESOLVED: "the reference could not be found on OpenAlex or Semantic Scholar",
                    ResolutionStatus.FAILED: f"the lookup failed ({ref.resolution.error})",
                    ResolutionStatus.NOT_ATTEMPTED: "the reference was not resolved",
                }[ref.resolution.status]
                findings.append(Finding(
                    type=FindingType.CLAIM_UNVERIFIABLE, severity="low",
                    title=f"Cannot verify claim against {ref_display(ref)}",
                    detail=f"Cannot check this citation: {reason}.",
                    section_id=cit.section_id,
                    section_title=section.title if section else None,
                    claim_text=claim, ref_ids=[ref_id],
                    verdict=Verdict.CANNOT_VERIFY, source=source,
                    provenance=f"resolution status: {ref.resolution.status.value}"))
                continue
            # ---- K4: no LLM — say so, don't fake it --------------------
            if llm is None:
                findings.append(Finding(
                    type=FindingType.CLAIM_UNVERIFIABLE, severity="info",
                    title=f"Claim check needs an LLM ({ref_display(ref)})",
                    detail="No LLM provider is configured, so the app cannot "
                           "judge whether this source supports the claim. "
                           "The abstract was fetched and is shown for manual review.",
                    section_id=cit.section_id,
                    section_title=section.title if section else None,
                    claim_text=claim, ref_ids=[ref_id],
                    verdict=Verdict.CANNOT_VERIFY, source=source,
                    provenance="abstract fetched; no LLM configured"))
                continue
            # ---- K3: judge --------------------------------------------
            try:
                data = llm.complete_json(
                    _JUDGE_SYSTEM,
                    f"CLAIM (from section “{section.title if section else '?'}”, "
                    f"citation {cit.raw}):\n{claim}\n\n"
                    f"CITED WORK: {ref.csl.get('title', ref_display(ref))}\n"
                    f"ABSTRACT:\n{ref.resolution.abstract[:2500]}")
            except LLMError as e:
                progress(f"Claim check LLM call failed for {ref_id}: {e}")
                findings.append(Finding(
                    type=FindingType.CLAIM_UNVERIFIABLE, severity="info",
                    title=f"Claim check failed for {ref_display(ref)}",
                    detail=f"LLM call failed: {e}", claim_text=claim,
                    section_id=cit.section_id, ref_ids=[ref_id],
                    verdict=Verdict.CANNOT_VERIFY, source=source))
                continue

            verdict_raw = str(data.get("verdict", "cannot_verify")) if isinstance(data, dict) else "cannot_verify"
            try:
                verdict = Verdict(verdict_raw)
            except ValueError:
                verdict = Verdict.CANNOT_VERIFY
            rationale = str(data.get("rationale", ""))[:600] if isinstance(data, dict) else ""
            quote = data.get("quote") if isinstance(data, dict) else None
            conf = data.get("confidence") if isinstance(data, dict) else None

            # anti-hallucination: the quote must exist in the abstract
            if quote:
                best = max((fuzz.partial_ratio(str(quote).lower(), ref.resolution.abstract.lower()), 0))
                if best < 85:
                    rationale += " (The model's supporting quote was not found in the abstract and was discarded.)"
                    quote = None

            ftype = {Verdict.SUPPORTS: FindingType.CLAIM_SUPPORTED,
                     Verdict.PARTIAL: FindingType.CLAIM_MISMATCH,
                     Verdict.DOES_NOT_SUPPORT: FindingType.CLAIM_MISMATCH,
                     Verdict.CANNOT_VERIFY: FindingType.CLAIM_UNVERIFIABLE}[verdict]
            severity = {Verdict.SUPPORTS: "info", Verdict.PARTIAL: "medium",
                        Verdict.DOES_NOT_SUPPORT: "high",
                        Verdict.CANNOT_VERIFY: "low"}[verdict]
            titles = {Verdict.SUPPORTS: "Citation checks out",
                      Verdict.PARTIAL: "Citation only partially supports the claim",
                      Verdict.DOES_NOT_SUPPORT: "Cited source does not support this claim",
                      Verdict.CANNOT_VERIFY: "Could not verify this citation"}
            findings.append(Finding(
                type=ftype, severity=severity,
                title=f"{titles[verdict]} — {ref_display(ref)}",
                detail=rationale,
                section_id=cit.section_id,
                section_title=section.title if section else None,
                claim_text=claim, ref_ids=[ref_id],
                verdict=verdict, verdict_rationale=rationale,
                evidence_quote=str(quote) if quote else None,
                source=source,
                provenance=f"abstract via {ref.resolution.source or 'resolution'}; "
                           f"judged by {llm.label}",
                confidence=float(conf) if isinstance(conf, (int, float)) else None,
                llm_used=llm.label))
            _ = src_url
    return findings


def ref_display(ref) -> str:
    if ref.parsed.authors:
        fam = ref.parsed.authors[0].split(",")[0]
        yr = f", {ref.parsed.year}" if ref.parsed.year else ""
        return f"{fam} et al.{yr}" if len(ref.parsed.authors) > 1 else f"{fam}{yr}"
    return ref.csl.get("title", ref.id)[:60]


def _source_from_ref(ref) -> ExternalSource | None:
    r = ref.resolution
    if r.source and r.source_url:
        return ExternalSource(
            api=r.source, api_id=r.source_id or "",
            title=ref.csl.get("title", ref.parsed.title or "(unknown)"),
            year=ref.parsed.year, authors=ref.parsed.authors[:10],
            doi=r.doi, url=r.source_url, abstract=r.abstract,
            csl=ref.csl)
    url = ref.best_url()
    if url:
        return ExternalSource(
            api="parsed", api_id=ref.id,
            title=ref.csl.get("title", ref.parsed.title or "(unknown)"),
            year=ref.parsed.year, authors=ref.parsed.authors[:10],
            doi=ref.parsed.doi, url=url, abstract=None, csl=ref.csl)
    return None
