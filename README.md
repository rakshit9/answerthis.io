# Paper Improvement Agent

Upload a research paper PDF → see exactly how it was parsed → get a peer
review grounded in **real** academic search (Semantic Scholar + OpenAlex) →
improve the paper with natural-language commands → export the revised paper
as LaTeX. Citations are represented canonically as **CSL-JSON**, rendered
through **citeproc** with real `.csl` styles, and protected by a citation-
integrity checker: no edit can silently drop a citation, and no citation can
enter the system without a real, linkable source.

**Start here:** [`docs/system-design.md`](docs/system-design.md) — the
citation-parsing pipeline and the agent architecture (the part weighed most
heavily). Also: [`docs/ai-use-and-verification.md`](docs/ai-use-and-verification.md)
and [`docs/limitations.md`](docs/limitations.md). Workflow screenshots are in
[`screenshots/`](screenshots/).

## How to run

Requirements: Python 3.11+, Node 18+.

```bash
# 1. backend
cd backend
pip install -r requirements.txt        # (or use a venv)
export OPENAI_API_KEY=sk-...           # or GEMINI_API_KEY=... (enables the agent
                                       #  + claim checks; app runs without, degraded honestly)
export S2_API_KEY=...                  # optional: raises Semantic Scholar rate limits
uvicorn app.main:app --port 8000

# 2. frontend (dev)
cd ../frontend
npm install
npm run dev                            # → http://localhost:5173  (proxies /api to :8000)
```

Production-ish single process: `npm run build` in `frontend/`, then uvicorn
serves the built app at http://localhost:8000.

Test with any real paper — arXiv PDFs work well (their references resolve on
both APIs). e.g. `curl -L -o paper.pdf https://arxiv.org/pdf/1706.03762`.

```bash
cd backend && python -m pytest tests/    # 63 tests for the core behaviors
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | — | LLM for the agent + claim checks. Pluggable: `PIA_LLM_PROVIDER=openai\|gemini\|auto` |
| `PIA_OPENAI_MODEL` / `PIA_GEMINI_MODEL` | `gpt-4o-mini` / `gemini-flash-latest` | model per provider |
| `S2_API_KEY` | — | optional Semantic Scholar key (free) — without it the shared pool is slow/429-prone |
| `OPENALEX_MAILTO` | example addr | puts OpenAlex calls in the polite pool |
| `PIA_MAX_QUERIES_PER_REVIEW` | 10 | cap on external searches per review |
| `PIA_MAX_CLAIM_CHECKS` | 12 | cap on claim–citation checks per review |

No LLM key? Parsing, resolution, rendering, keyword-search-based missing-work
review, and export all still work; claim verdicts and editing report honestly
that they need an LLM instead of faking output.

## The workflow

1. **Upload & parse** — the first screen is the upload. The parse view shows
   the pipeline stage log, detected structure, in-text citation style (with
   confidence), and every reference with parsed fields + confidence;
   unparseable entries are kept and flagged, not dropped. "Resolve" matches
   references to OpenAlex/Semantic Scholar records (DOI → arXiv → title
   ladder) with per-reference status and links.
2. **Read** — the paper rendered with citeproc-formatted citation labels in
   the selected CSL style (APA, IEEE, Chicago, Harvard, Nature vendored;
   detected style is preselected).
3. **Peer review** — runs missing-work search (both APIs, deduped against
   your bibliography, ranked) and claim–citation checks (cited abstract vs
   your sentence, verdict + verbatim quote, quote verified against the
   abstract). Every finding links to a real source and states its
   provenance, including which searches failed.
4. **Edit** — commands like *"add more citations to the introduction"* or
   *"make the intro shorter"*. The agent plans typed operations, searches the
   real APIs, and produces a proposal: per-section diffs, new references with
   sources, an integrity report. You approve each change; violations are
   unapplyable by construction.
5. **Export** — a LaTeX project zip: `main.tex` (natbib/cite commands +
   citeproc-rendered bibliography), `references.bib`, `paper.md`,
   `paper.json` (the full canonical model), `PROVENANCE.md` (every
   agent-added source + edit history).

## Project layout

```
backend/app/
  parsing/    A–E pipeline: pdf_extract → structure → reflist → refparse → intext
  models/     PaperDocument (token-bearing sections), Reference (CSL-JSON canonical),
              findings, proposals, integrity reports
  external/   OpenAlex + Semantic Scholar clients, disk cache, resolution ladder
  cslproc/    citeproc rendering + vendored .csl styles
  llm/        pluggable providers (OpenAI, Gemini, mock)
  review/     claim–citation checks + missing-work search
  agent/      planner → typed ops → integrity checker → apply
  export/     LaTeX / BibTeX / Markdown / provenance
  api/        FastAPI routes; store.py = on-disk JSON persistence
backend/tests/  63 pytest tests incl. a synthetic-PDF integration test
frontend/       React + TS: upload → parse → read → review → edit (diff+approve) → export
```
