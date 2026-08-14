# AI tools: where they were used, and what was verified

## Where AI was used

This project was built with **Claude (Anthropic)** working in an agentic
coding session (Claude's Cowork/Claude Code tooling), directed and reviewed
by me. Concretely:

- **All application code** (backend pipeline, agent, API, frontend) was
  drafted by Claude from my requirements and the assessment brief, iterating
  under failing runs and tests.
- **The system design itself** (staged parsing pipeline, citation tokens,
  typed agent ops, integrity invariants) was developed in the session as an
  explicit design conversation before/while coding — it is documented in
  `docs/system-design.md`.
- **Tests** were written by Claude alongside the code; several of them were
  written specifically to pin down bugs found while running the pipeline on
  real papers (e.g. the `Duchi, John, Hazan, Elad` author-pairing case, the
  `Science, 313(5786)` fake-year case, initials-boundary title splitting).

The app itself also uses LLMs **at runtime** (OpenAI or Gemini, pluggable)
for: review query building, claim-support verdicts, relevance ranking,
edit planning, and constrained rewrites. Runtime LLM output is never trusted
blindly — see the verification section of the system design (verbatim-quote
checking against abstracts, claim-sentence existence checks, token-multiset
validation, and the source-provenance requirement for any new citation).

## What was verified, and how

- **Automated tests:** 63 pytest tests covering in-text detection across
  styles (numeric, ranges, author-year parenthetical/narrative/disambiguated,
  superscript guard), reference segmentation strategies, entry parsing across
  IEEE/APA/numbered/family-first/Vancouver styles, CSL-JSON conversion,
  resolution ladder + honest failure, integrity checker (loss, unknown refs,
  provenance, acknowledged removals), apply semantics (approved subsets,
  stale-base guard, pruning), agent flows with a scripted LLM (token
  preservation, retry-then-fail, provenance of inserted citations, dedupe,
  refusal), CSL rendering per style, LaTeX/BibTeX export, and an end-to-end
  synthetic-PDF integration test. `python -m pytest tests/` — all green.
- **Real-paper runs:** the full parse pipeline was run repeatedly on two real
  arXiv papers with *different* citation styles — *Attention Is All You Need*
  (numeric brackets, 40/40 references parsed, 63 in-text groups linked, 0
  unmatched) and *Adam* (author–year natbib, 23 references parsed, 28 groups
  linked including `2012a/b`-style disambiguation, 0 unmatched) — and outputs
  were manually inspected at each pipeline stage during development.
- **Manual UI walkthrough:** the full workflow (upload → parse inspection →
  resolution → review → edit proposal with diff/approval → LaTeX export) was
  exercised in the browser; the screenshots in `screenshots/` are from those
  runs, not mockups.
- **Honesty paths were tested deliberately:** running with no LLM key (claim
  checks and editing must say so, not fake it), simulated API 429s (must
  become visible findings), fabricated LLM quotes (must be discarded), and
  edits that drop citations (must be blocked).

## Honest notes

- The development sandbox's shared egress IP exhausted the free-tier budgets
  of both academic APIs during part of development, so a portion of API-layer
  testing ran against recorded response fixtures matching the real schemas;
  client behavior on live 429s (backoff → honest failure) was exercised for
  real. Nothing about the client code is fixture-specific — point it at the
  live APIs (ideally with `S2_API_KEY` set) and it behaves identically, with
  every response cached on disk.
- I did not hand-write the code line-by-line; I reviewed the architecture,
  drove the iteration, and verified behavior through the tests and runs
  described above.
