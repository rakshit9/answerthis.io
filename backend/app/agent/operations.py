"""Agent step 2: executing planned operations.

Both operations produce *proposed* section texts — nothing touches the
document until the user approves and ``apply`` runs.

find_citations
  F1. Pick claim sentences (LLM returns exact sentences; each is verified
      to exist in the section — a sentence the model made up is rejected).
  F2. Build a search query per claim and run it on OpenAlex + Semantic
      Scholar (same clients, caching and honesty rules as the review).
  F3. De-duplicate against the existing bibliography, rank, keep the best.
  F4. Create agent-added ``Reference`` objects whose CSL comes from the API
      record (with full provenance) and append ``[[citep:ref_N]]`` tokens
      at the end of the claim sentence.

rewrite_section
  W1. LLM rewrites the token-bearing text under hard token-preservation
      rules.
  W2. The token multiset is validated; one corrective retry; if it still
      differs the change is marked failed — it cannot be approved.
"""
from __future__ import annotations

import re

from ..external import openalex, semantic_scholar
from ..external.cache import ApiError
from ..llm.base import LLMError, LLMProvider
from ..models.core import (PaperDocument, Reference, ParsedFields, Resolution,
                           ResolutionStatus, Section, extract_token_ref_ids,
                           make_cite_token)
from ..models.edits import AgentStep, CitationAdd, EditProposal, SectionChange
from ..models.findings import ExternalSource
from ..parsing.textutil import sentence_spans
from ..review.missing import already_cited, rank_candidates

_CLAIM_SYSTEM = """You select sentences in a paper section that would benefit \
from a supporting citation. Return JSON:
{"claims": [{"sentence": "<EXACT sentence copied verbatim from the text>",
             "query": "<3-8 keyword search query for finding supporting work>"}]}
Rules:
- Copy sentences EXACTLY (you may omit citation tokens like [[citep:ref_3]]
  when copying — they will be matched flexibly).
- Prefer factual assertions currently lacking a citation token.
- At most {n} claims, each from a different part of the section."""


def op_find_citations(doc: PaperDocument, section: Section, topic: str,
                      max_new: int, llm: LLMProvider | None,
                      proposal: EditProposal, working_text: str,
                      next_ref_num: int) -> tuple[str, int]:
    """Returns (new_working_text, next_ref_num). Appends steps/refs/adds to
    the proposal as it goes."""

    def step(kind: str, text: str, **data) -> None:
        proposal.steps.append(AgentStep(kind=kind, text=text, data=data))

    # ---- F1: claim sites ---------------------------------------------
    claims: list[dict] = []
    if llm is not None:
        try:
            data = llm.complete_json(
                _CLAIM_SYSTEM.replace("{n}", str(max_new)),
                (f"Section “{section.title}”"
                 + (f" — the user asked for support on: {topic}" if topic else "")
                 + f"\n\nText:\n{working_text[:6000]}"))
            claims = [c for c in (data.get("claims", []) if isinstance(data, dict) else [])
                      if isinstance(c, dict) and c.get("sentence") and c.get("query")]
        except LLMError as e:
            step("error", f"Claim selection LLM call failed: {e}")
    if not claims:
        # honest fallback: anchor on the section's first long sentence
        spans = [s for s in sentence_spans(working_text)
                 if len(working_text[s[0]:s[1]]) > 60]
        if spans:
            s0 = working_text[spans[0][0]:spans[0][1]]
            claims = [{"sentence": s0,
                       "query": (topic or f"{section.title} {doc.meta.title}")[:120]}]
            step("plan", "No LLM claim selection — anchoring on the section's "
                         "first substantive sentence (labelled fallback)")

    new_text = working_text
    used_queries: set[str] = set()
    added = 0
    for claim in claims:
        if added >= max_new:
            break
        sentence = str(claim["sentence"]).strip()
        query = str(claim["query"]).strip()[:150]
        if not query or query.lower() in used_queries:
            continue
        used_queries.add(query.lower())

        anchor = _locate_sentence(new_text, sentence)
        if anchor is None:
            step("error", f"Model-selected claim sentence not found in section; "
                          f"skipped: “{sentence[:80]}…”")
            continue

        # ---- F2: search ------------------------------------------------
        candidates: list[ExternalSource] = []
        for api_name, fn in (("openalex", openalex.search),
                             ("semantic_scholar", semantic_scholar.search)):
            try:
                res = fn(query, 6)
                step("search", f"{api_name}: “{query}” → {len(res)} results",
                     api=api_name, query=query, n=len(res))
                candidates.extend(res)
            except ApiError as e:
                step("error", f"{api_name} search failed for “{query}”: {e}")

        # ---- F3: dedupe + rank ----------------------------------------
        fresh: list[ExternalSource] = []
        seen: set[str] = set()
        for c in candidates:
            key = (c.doi or "").lower() or "t:" + c.title.lower()[:80]
            if key in seen or already_cited(c, doc):
                continue
            # also avoid re-adding something this proposal already added
            if any(r.csl.get("title", "").lower() == c.title.lower()
                   for r in proposal.new_references):
                continue
            seen.add(key)
            fresh.append(c)
        ranked = rank_candidates(llm, sentence, fresh)
        best = [c for c, score, _ in ranked[:1] if score >= 0.5]
        if not best:
            step("check", f"No sufficiently relevant new source found for "
                          f"“{sentence[:70]}…” — nothing inserted (honest miss)")
            continue
        src = best[0]
        score = ranked[0][1]

        # ---- F4: create reference + insert token ----------------------
        ref_id = f"ref_{next_ref_num}"
        next_ref_num += 1
        csl = dict(src.csl)
        csl["id"] = ref_id
        new_ref = Reference(
            id=ref_id, raw_text=f"[agent-added] {src.title}",
            parsed=ParsedFields(
                authors=[_family_first(a) for a in src.authors[:12]],
                year=src.year, title=src.title, container=src.venue,
                doi=src.doi, url=src.url),
            parse_confidence=1.0, csl=csl,
            resolution=Resolution(
                status=ResolutionStatus.RESOLVED, source=src.api,
                source_id=src.api_id, source_url=src.url, doi=src.doi,
                match_score=1.0, method="agent_search", abstract=src.abstract),
            added_by="agent",
            added_reason=f"Supports: “{sentence[:160]}” (query: “{query}”)")
        proposal.new_references.append(new_ref)
        proposal.citation_adds.append(CitationAdd(
            ref_id=ref_id,
            reason=f"Relevance {score:.2f} for claim “{sentence[:120]}”",
            api=src.api, source_url=src.url, anchor_text=sentence[:200]))
        token = make_cite_token([ref_id])
        new_text = _insert_token_at_sentence_end(new_text, anchor, token)
        step("draft", f"Insert {token} — “{src.title}” ({src.year}, {src.api})",
             ref_id=ref_id, url=src.url)
        added += 1

    if added == 0:
        step("check", "find_citations finished with no insertions")
    return new_text, next_ref_num


_REWRITE_SYSTEM = """You rewrite one section of a research paper following an \
instruction. The text contains citation tokens like [[citep:ref_3]] or \
[[citet:ref_7,ref_9]].

HARD RULES — breaking any of them makes the output unusable:
1. Every citation token in the input MUST appear in the output, byte-for-byte
   identical, exactly as many times as in the input. Never drop, merge, split,
   renumber or invent tokens.
2. Keep each token attached to the statement it supports. If you condense two
   sentences into one, their tokens all move onto the surviving statement.
3. Do not add facts, results, numbers, or claims that are not in the input.
4. Keep LaTeX-ish inline math and technical notation as-is.
Return JSON: {"text": "<the rewritten section text>", "rationale": "<1-2 sentences>"}"""


def op_rewrite_section(section: Section, instruction: str,
                       llm: LLMProvider, proposal: EditProposal,
                       working_text: str) -> str | None:
    """Returns the rewritten text, or None if it could not be done safely."""

    def step(kind: str, text: str, **data) -> None:
        proposal.steps.append(AgentStep(kind=kind, text=text, data=data))

    want = sorted(extract_token_ref_ids(working_text))
    attempt_text = working_text
    feedback = ""
    for attempt in (1, 2):
        try:
            data = llm.complete_json(
                _REWRITE_SYSTEM,
                f"Instruction: {instruction}\n{feedback}\n"
                f"Section “{section.title}” text:\n{attempt_text}",
                max_tokens=6000)
        except LLMError as e:
            step("error", f"Rewrite LLM call failed: {e}")
            return None
        text = data.get("text") if isinstance(data, dict) else None
        if not text or not isinstance(text, str):
            step("error", "Rewrite returned no text")
            return None
        got = sorted(extract_token_ref_ids(text))
        if got == want:
            step("draft", f"Rewrite of “{section.title}” ok on attempt {attempt} "
                          f"({len(working_text)} → {len(text)} chars); "
                          f"all {len(want)} citation tokens preserved",
                 rationale=str(data.get("rationale", ""))[:300])
            return text.strip()
        missing = _multiset_diff(want, got)
        extra = _multiset_diff(got, want)
        step("check", f"Attempt {attempt}: token mismatch (missing: {missing}, "
                      f"unexpected: {extra}) — "
                      + ("retrying with explicit correction" if attempt == 1
                         else "giving up; change marked as failed"))
        feedback = (f"\nYOUR PREVIOUS ATTEMPT BROKE RULE 1. "
                    f"Missing tokens that MUST reappear: "
                    f"{[make_cite_token([m]) for m in missing]}; "
                    f"tokens you invented that MUST NOT appear: {extra}. "
                    f"Rewrite again, preserving every original token.\n")
    return None


# ---------------------------------------------------------------- helpers --

def _family_first(name: str) -> str:
    parts = name.rsplit(" ", 1)
    return f"{parts[1]}, {parts[0]}" if len(parts) == 2 else name


def _norm_for_match(s: str) -> str:
    from ..models.core import CITE_TOKEN_RE
    s = CITE_TOKEN_RE.sub("", s)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _locate_sentence(text: str, sentence: str) -> tuple[int, int] | None:
    """Find the sentence's span in ``text`` (token-insensitive, fuzzy)."""
    target = _norm_for_match(sentence)
    if not target:
        return None
    best: tuple[int, int] | None = None
    best_score = 0.0
    from rapidfuzz import fuzz
    for s, e in sentence_spans(text):
        cand = _norm_for_match(text[s:e])
        if not cand:
            continue
        score = fuzz.ratio(cand, target) / 100.0
        if score > best_score:
            best_score = score
            best = (s, e)
    return best if best_score >= 0.75 else None


def _insert_token_at_sentence_end(text: str, span: tuple[int, int],
                                  token: str) -> str:
    s, e = span
    sent = text[s:e]
    m = re.search(r"[.!?]\s*$", sent)
    if m:
        insert_at = s + m.start()
        return text[:insert_at].rstrip() + " " + token + text[insert_at:]
    return text[:e].rstrip() + " " + token + text[e:]


def _multiset_diff(a: list[str], b: list[str]) -> list[str]:
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    out = []
    for k, v in ca.items():
        out.extend([k] * max(0, v - cb.get(k, 0)))
    return out
