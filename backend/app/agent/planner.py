"""Agent step 1: natural-language command → typed, validated plan.

The op vocabulary is deliberately small and typed — the LLM chooses and
parameterizes operations, it does not free-form edit the paper:

  find_citations   {section_id, topic?, max_new}   search real APIs, insert
                                                   citations at claim sites
  rewrite_section  {section_id, instruction}       constrained rewrite that
                                                   must preserve tokens

An invalid plan (unknown op, unknown section) fails loudly in the proposal
instead of being silently "fixed".
"""
from __future__ import annotations

from ..llm.base import LLMError, LLMProvider
from ..models.core import CITE_TOKEN_RE, PaperDocument, SectionKind

PLANNER_SYSTEM = """You are the planning module of a paper-editing agent. \
Turn the user's command into a short plan over these operations ONLY:

1. {"op": "find_citations", "section_id": "...", "topic": "<what to find \
support for; empty = let the executor pick claim sentences>", "max_new": 1-5}
   Use when the user wants more/better citations somewhere.
2. {"op": "rewrite_section", "section_id": "...", "instruction": "<precise \
editing instruction>"}
   Use for shortening, clarifying, tightening, restructuring prose.

Return JSON:
{"plan": "<1-3 sentences describing what you will do>",
 "operations": [ ... at most 4 ... ]}

Rules:
- Only use section_ids from the provided list.
- If the command maps to nothing (e.g. "delete all references", "make up
  results"), return {"plan": "<why you refuse>", "operations": []}.
- Never plan to remove citations; rewrites must keep them."""


class PlanError(Exception):
    pass


def make_plan(llm: LLMProvider, doc: PaperDocument, command: str) -> dict:
    sections = "\n".join(
        f"- {s.id}: “{s.title}” ({s.kind.value}, {len(s.content)} chars, "
        f"{len(CITE_TOKEN_RE.findall(s.content))} citation tokens)"
        for s in doc.sections if s.kind in (SectionKind.BODY, SectionKind.ABSTRACT))
    user = (f"Paper: {doc.meta.title}\n\nSections:\n{sections}\n\n"
            f"User command: {command!r}")
    try:
        data = llm.complete_json(PLANNER_SYSTEM, user)
    except LLMError as e:
        raise PlanError(f"Planner LLM call failed: {e}") from e
    if not isinstance(data, dict) or "operations" not in data:
        raise PlanError(f"Planner returned malformed plan: {str(data)[:200]}")
    ops = data.get("operations") or []
    if not isinstance(ops, list):
        raise PlanError("Planner 'operations' is not a list")

    valid_ids = {s.id for s in doc.sections}
    cleaned = []
    for op in ops[:4]:
        if not isinstance(op, dict):
            raise PlanError(f"Malformed operation: {op!r}")
        kind = op.get("op")
        sid = op.get("section_id", "")
        if sid not in valid_ids:
            raise PlanError(f"Plan references unknown section {sid!r}")
        if kind == "find_citations":
            cleaned.append({"op": "find_citations", "section_id": sid,
                            "topic": str(op.get("topic", ""))[:400],
                            "max_new": max(1, min(5, int(op.get("max_new", 3))))})
        elif kind == "rewrite_section":
            instr = str(op.get("instruction", "")).strip()
            if not instr:
                raise PlanError("rewrite_section without instruction")
            cleaned.append({"op": "rewrite_section", "section_id": sid,
                            "instruction": instr[:600]})
        else:
            raise PlanError(f"Unknown operation {kind!r}")
    return {"plan": str(data.get("plan", ""))[:800], "operations": cleaned}
