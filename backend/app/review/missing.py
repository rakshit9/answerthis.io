"""Missing-work review: find papers the manuscript should plausibly cite.

Pipeline per section:
  M1. Build search queries — with the LLM (claims/topics extracted per
      section) or, without one, from title + heading + keyphrases (the
      provenance string says which, so a heuristic search is never dressed
      up as a semantic one).
  M2. Run each query on BOTH OpenAlex and Semantic Scholar. API failures
      become SEARCH_FAILURE findings, not empty silence.
  M3. Drop candidates the paper already cites (DOI / arXiv / fuzzy title
      match against the reference list) and near-duplicates of the paper
      itself.
  M4. Rank what's left (LLM relevance rating when available, otherwise
      citation count + keyword overlap — again, labelled) and emit
      MISSING_WORK findings, each carrying the real ExternalSource.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..config import settings
from ..external import openalex, semantic_scholar
from ..external.cache import ApiError
from ..external.resolve import title_similarity
from ..llm.base import LLMError, LLMProvider
from ..models.core import PaperDocument, Section, SectionKind
from ..models.findings import ExternalSource, Finding, FindingType

_STOP = set("""a an the of and or to in for with on by is are was were be been this
that these those we our us it its as from at which who whose can could may might
using use used new novel approach method paper propose proposed present show shows
result results state art""".split())


def build_queries_heuristic(doc: PaperDocument, section: Section,
                            n: int = 2) -> list[dict]:
    """Keyphrase queries. Provenance is explicit about being heuristic."""
    text = section.content[:4000]
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    grams: Counter[str] = Counter()
    for i in range(len(words) - 1):
        if words[i] in _STOP or words[i + 1] in _STOP:
            continue
        grams[f"{words[i]} {words[i + 1]}"] += 1
    top = [g for g, c in grams.most_common(6) if c >= 2][:n]
    queries = []
    title_head = " ".join(re.findall(r"[A-Za-z][A-Za-z\-]+", doc.meta.title)[:6])
    for phrase in top:
        queries.append({
            "query": f"{phrase} {title_head}".strip()[:120],
            "claim": f"Topic of section “{section.title}”: {phrase}",
            "method": "heuristic keyphrases (no LLM configured)"})
    if not queries and section.title:
        queries.append({"query": f"{section.title} {title_head}"[:120],
                        "claim": f"Section topic: {section.title}",
                        "method": "heuristic section title (no LLM configured)"})
    return queries


_QUERY_SYSTEM = """You help peer-review a research paper by finding related work \
the authors may have missed. Given one section of the paper, produce search \
queries for an academic search engine (keyword search over titles/abstracts).
Return JSON: {"queries": [{"query": "...", "claim": "..."}]}
- "query": 3-10 keywords, no quotes/boolean operators.
- "claim": the specific claim or topic in the section this query checks, quoted
  or closely paraphrased from the section.
Make each query about a DIFFERENT claim/topic. Prefer claims that sound like
they need supporting or contrasting citations."""


def build_queries_llm(llm: LLMProvider, doc: PaperDocument, section: Section,
                      n: int = 3) -> list[dict]:
    user = (f"Paper title: {doc.meta.title}\n"
            f"Abstract: {doc.meta.abstract[:1200]}\n\n"
            f"Section “{section.title}”:\n{section.content[:5000]}\n\n"
            f"Give up to {n} queries.")
    data = llm.complete_json(_QUERY_SYSTEM, user)
    queries = data.get("queries", []) if isinstance(data, dict) else []
    out = []
    for q in queries[:n]:
        if isinstance(q, dict) and q.get("query"):
            out.append({"query": str(q["query"])[:120],
                        "claim": str(q.get("claim", ""))[:400],
                        "method": f"LLM query builder ({llm.label})"})
    return out


def already_cited(cand: ExternalSource, doc: PaperDocument) -> bool:
    for ref in doc.references:
        if cand.doi and (ref.parsed.doi or ref.resolution.doi):
            have = (ref.resolution.doi or ref.parsed.doi or "").lower()
            if have and have == cand.doi.lower():
                return True
        arxiv = ref.parsed.arxiv_id
        if arxiv and arxiv in (cand.url or "") + str(cand.csl.get("note", "")):
            return True
        t = ref.parsed.title or ref.csl.get("title") or ""
        if t and title_similarity(t, cand.title) >= 0.90:
            return True
    # the paper itself
    if title_similarity(doc.meta.title, cand.title) >= 0.93:
        return True
    return False


_RELEVANCE_SYSTEM = """You rate whether a found paper is genuinely relevant for a \
manuscript to cite. Return JSON: {"ratings": [{"i": <index>, "score": 0-3, \
"why": "..."}]}. 3 = clearly should be cited for this claim; 2 = probably \
relevant; 1 = tangential; 0 = irrelevant. Judge ONLY from the given titles/abstracts."""


def rank_candidates(llm: LLMProvider | None, claim: str,
                    cands: list[ExternalSource]) -> list[tuple[ExternalSource, float, str]]:
    """→ [(candidate, score0..1, why)] sorted desc."""
    if not cands:
        return []
    if llm is not None:
        listing = "\n".join(
            f"[{i}] {c.title} ({c.year}) — {(c.abstract or '(no abstract)')[:400]}"
            for i, c in enumerate(cands))
        try:
            data = llm.complete_json(
                _RELEVANCE_SYSTEM,
                f"Claim/topic from the manuscript:\n{claim}\n\nFound papers:\n{listing}")
            ratings = {int(r["i"]): (float(r["score"]), str(r.get("why", "")))
                       for r in data.get("ratings", []) if "i" in r and "score" in r}
            scored = [(c, ratings.get(i, (0.0, ""))[0] / 3.0, ratings.get(i, (0.0, ""))[1])
                      for i, c in enumerate(cands)]
            return sorted(scored, key=lambda x: -x[1])
        except LLMError:
            pass                      # fall through to the labelled heuristic
    claim_words = {w for w in re.findall(r"[a-z\-]{3,}", claim.lower())} - _STOP
    scored_h = []
    for c in cands:
        text = (c.title + " " + (c.abstract or "")).lower()
        overlap = sum(1 for w in claim_words if w in text) / max(3, len(claim_words))
        pop = math.log10((c.cited_by_count or 0) + 1) / 5
        scored_h.append((c, min(1.0, 0.7 * overlap + 0.3 * pop),
                         "keyword-overlap ranking (no LLM)"))
    return sorted(scored_h, key=lambda x: -x[1])


def find_missing_work(doc: PaperDocument, llm: LLMProvider | None,
                      sections: list[Section], progress, max_queries: int,
                      max_findings: int = 8) -> list[Finding]:
    findings: list[Finding] = []
    queries: list[tuple[Section, dict]] = []

    for sec in sections:
        if sec.kind not in (SectionKind.BODY, SectionKind.ABSTRACT) or len(sec.content) < 200:
            continue
        per_sec: list[dict] = []
        if llm is not None:
            try:
                per_sec = build_queries_llm(llm, doc, sec)
            except LLMError as e:
                progress(f"LLM query building failed for “{sec.title}”: {e} — "
                         f"falling back to heuristic queries")
        if not per_sec:
            per_sec = build_queries_heuristic(doc, sec)
        for q in per_sec:
            queries.append((sec, q))

    queries = queries[:max_queries]
    progress(f"Missing-work search: {len(queries)} queries across "
             f"{len({s.id for s, _ in queries})} sections")

    seen_keys: set[str] = set()
    candidates: list[tuple[Section, dict, ExternalSource]] = []
    for sec, q in queries:
        for api, fn in (("openalex", openalex.search), ("semantic_scholar", semantic_scholar.search)):
            try:
                results = fn(q["query"], 8)
                progress(f"{api} search “{q['query']}” → {len(results)} results")
            except ApiError as e:
                progress(f"{api} search “{q['query']}” FAILED: {e}")
                findings.append(Finding(
                    type=FindingType.SEARCH_FAILURE, severity="info",
                    title=f"{api} search failed",
                    detail=str(e), section_id=sec.id, section_title=sec.title,
                    provenance=f"{api} search: “{q['query']}”"))
                continue
            for c in results:
                key = (c.doi or "").lower() or ("t:" + c.title.lower()[:80])
                if key in seen_keys or already_cited(c, doc):
                    continue
                seen_keys.add(key)
                candidates.append((sec, q, c))

    progress(f"{len(candidates)} new candidate papers after de-duplication "
             f"against the existing reference list")

    # rank per claim, then keep the global best
    per_claim: dict[str, list] = {}
    for sec, q, c in candidates:
        per_claim.setdefault(q["claim"], []).append((sec, q, c))
    ranked_all: list[tuple[Section, dict, ExternalSource, float, str]] = []
    for claim, group in per_claim.items():
        ranked = rank_candidates(llm, claim, [c for _, _, c in group])
        by_key = {id(c): (s, q) for s, q, c in group}
        for c, score, why in ranked[:3]:
            sec, q = by_key[id(c)]
            ranked_all.append((sec, q, c, score, why))
    ranked_all.sort(key=lambda x: -x[3])

    for sec, q, c, score, why in ranked_all[:max_findings]:
        if score < 0.4:
            continue
        findings.append(Finding(
            type=FindingType.MISSING_WORK,
            severity="medium" if score >= 0.67 else "low",
            title=f"Possibly missing citation: “{c.title}”"
                  + (f" ({c.year})" if c.year else ""),
            detail=(why or "Related to this section's topic.")
                   + (f" Cited by {c.cited_by_count}." if c.cited_by_count else ""),
            section_id=sec.id, section_title=sec.title,
            claim_text=q["claim"],
            source=c,
            provenance=f"{c.api} search: “{q['query']}” [{q['method']}]",
            confidence=round(score, 2),
            llm_used=llm.label if llm else None))
    return findings
