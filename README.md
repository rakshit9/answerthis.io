# Paper Improvement Agent

Upload a research paper PDF → see exactly how it was parsed → get a peer
review grounded in **real** academic search (Semantic Scholar + OpenAlex) →
improve the paper with natural-language commands → export the revised paper
as LaTeX. Citations are canonically **CSL-JSON**, rendered through
**citeproc** with real `.csl` styles, and protected by a citation-integrity
checker: no edit can silently drop a citation, and no citation can enter the
system without a real, linkable source.

## Watch it

<p align="center">
  <a href="screenshots/feature-tour.mp4">
    <img src="screenshots/feature-tour-preview.gif" alt="Feature tour" width="760">
  </a>
</p>

<p align="center">
  <b><a href="screenshots/feature-tour.mp4">▶ Full feature tour — 3.8 min, with narration</a></b>
</p>

The loop above plays right here — five moments from the tour, silent: the
parse stages landing one by one, a citation jumping to its entry, review
findings against live search, approving a diff, and the LaTeX view. Click it,
or the link, for the narrated film: GitHub strips `<video>` out of README
files, so the full version opens on its own page, where it plays in the
browser. No download either way.

The whole workflow on a real 24-page paper: upload and the six parse stages,
what the parser found and what it refused, citations as links, peer review
against live academic search, accepting a finding as a citation, editing by
command with the diff and integrity check, the editable LaTeX view, and
export. Built with [Remotion](https://github.com/remotion-dev/remotion) —
source and script in [`video/`](video), screenshots in
[`screenshots/`](screenshots).

## System design

The two pieces the brief asks about — **citation parsing** and **the agent** —
with the full write-up and all eight diagrams in
**[`docs/system-design.md`](docs/system-design.md)**. The shape of the whole
system:

```mermaid
flowchart LR
    PDF[/"PDF upload"/] --> GATE{{"A0 · readability gate"}}
    GATE -->|"encrypted · no text layer"| REJECT["refused with a reason<br/>(never an empty parse)"]

    subgraph Parsing["1 · Citation parsing — deterministic, no LLM"]
        direction TB
        GATE -->|readable| A["A · layout extraction"]
        A --> AF["A′ · float capture"]
        AF --> B["B · structure"]
        B --> C["C · reference list"]
        C --> D["D · entry parsing"]
        B --> E["E · in-text markers"]
        D --> E
    end

    E --> DOC[("PaperDocument<br/><b>the canonical model</b><br/>sections carry citation tokens<br/>references are CSL-JSON")]

    subgraph Agent["2 · The agent — LLM-planned, API-grounded, human-approved"]
        direction TB
        REV["peer review<br/>missing work · claim checks"]
        EDIT["NL editing<br/>plan → typed ops"]
        PROP["EditProposal<br/>diffs + new refs + step log"]
        INT{{"citation-integrity check<br/>I1 · I2 · I3"}}
        OK["per-change human approval"]
        REV -.->|"“Cite this”"| PROP
        EDIT --> PROP --> INT
        INT -->|violation| BLOCKED["unapplyable by construction"]
        INT -->|clean| OK
    end

    DOC --> REV
    DOC --> EDIT
    OK --> APPLY["snapshot version → apply<br/>→ recompute in-text"] --> DOC

    subgraph Ext["External boundary — one client, cached, rate-limited"]
        S2[("Semantic Scholar")]
        OA[("OpenAlex")]
    end
    REV <--> Ext
    EDIT <--> Ext

    DOC --> RENDER["citeproc + vendored .csl"]
    RENDER --> READER["reader view"]
    RENDER --> EXPORT["LaTeX · BibTeX · Markdown · provenance"]

    style DOC fill:#beff50,stroke:#14140f,color:#14140f
    style REJECT stroke-dasharray: 4 3
    style BLOCKED stroke-dasharray: 4 3
```

Two invariants hold it together, and every arrow above is arranged to protect
them:

| Invariant | Enforced by |
|---|---|
| No citation is invented — every one traces to a real record | the external boundary is the *only* source of new references; integrity rule **I3** rejects any that arrives without provenance |
| No edit silently breaks a citation | citations live as **tokens** inside the text; rules **I1/I2** compare token multisets before and after, and a violating proposal cannot be applied |

**Read next:** [citation parsing](docs/system-design.md#piece-1--citation-parsing)
— pipeline stages, the intermediate representation between each, where
CSL-JSON sits, style detection and failure handling ·
[the agent](docs/system-design.md#piece-2--the-agent) — command → typed
operations, the Semantic Scholar / OpenAlex boundary, peer review, and how
citations stay intact across edits.

## Run it — Docker

Nothing but Docker needed (Compose v2). One process serves both the API and
the built frontend. Verified end to end: image builds, container reports
healthy, a real PDF parses inside it.

```bash
cp backend/.env.example backend/.env   # optional: add an OpenAI key, see Keys
docker compose up --build
```

Open **http://localhost:8000** and drop a PDF on the first screen. arXiv
papers work best — their references resolve on both APIs:

```bash
curl -L -o paper.pdf https://arxiv.org/pdf/1706.03762
```

Parsed papers live in `backend/data/`, mounted as a volume, so they survive
`docker compose down`. Keys are read from `backend/.env` at run time and are
never baked into the image. Use another port with `PIA_PORT=9000 docker
compose up`.

```bash
docker compose up -d --build     # background
docker compose logs -f           # follow logs
docker compose down              # stop (papers persist)
```

Updating is `git pull && docker compose up --build -d`. Dependency changes
rebuild automatically; the layer order means editing Python or TSX doesn't
reinstall anything.

## Run it — without Docker

For frontend hot-reload while developing. Requirements: Python 3.11+, Node
18+.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                   # → http://localhost:5173, proxies /api to :8000
```

`PIA_BACKEND_URL` repoints the dev server if the backend isn't on :8000.
For a single process instead, `npm run build` in `frontend/` and the uvicorn
command above serves the built app at http://localhost:8000.

**Tests:**

```bash
cd backend && .venv/bin/python -m pytest tests/    # 123 tests, no network
docker compose run --rm app python -m pytest tests/    # or in the image
```

## Keys

All optional — put them in `backend/.env` (gitignored; `.env.example` lists
them). An exported shell variable overrides the file.

| Key | Effect if missing |
|---|---|
| `OPENAI_API_KEY` *(or `GEMINI_API_KEY`)* | Parsing, rendering, review search and export still work. Claim verdicts and agentic editing say they need an LLM rather than faking output. |
| `S2_API_KEY` | Semantic Scholar still works on the shared pool — slower and 429-prone. Free key, worth having. |
| `OPENALEX_MAILTO` | OpenAlex works without any key; this just puts calls in the polite pool. |

Check what the app actually has: `curl localhost:8000/api/health`.

<details>
<summary>Other settings (all have working defaults)</summary>

| Env var | Default | Meaning |
|---|---|---|
| `PIA_LLM_PROVIDER` | `auto` | `openai` \| `gemini` \| `auto` (first key present, prefers OpenAI) |
| `PIA_OPENAI_MODEL` / `PIA_GEMINI_MODEL` | `gpt-4o-mini` / `gemini-flash-latest` | model per provider |
| `PIA_MAX_QUERIES_PER_REVIEW` | 10 | cap on external searches per review |
| `PIA_MAX_CLAIM_CHECKS` | 12 | cap on claim–citation checks per review |
| `PIA_HTTP_MAX_RETRIES` | 3 | retries per external GET on transient 429/5xx. Raise it (e.g. `15`) on the *shared* unauthenticated Semantic Scholar pool. Quota-exhausted responses (OpenAlex "Insufficient budget") are never retried — they fail fast and are reported. |
| `PIA_HTTP_BACKOFF_CAP` | 10 | max seconds for one backoff sleep |
| `PIA_PARSE_MIN_SECONDS` | 0 | pads the parse so the stage view is legible in a demo; off by default |

</details>

## What it does

1. **Upload & parse.** The parse view narrates the pipeline's own stages
   (A → A′ → B → C → D → E) as they run, then shows the detected structure,
   the in-text citation style with confidence, and every reference with its
   parsed fields. Unparseable entries are kept and flagged, never dropped.
   Figures, tables and boxed panels are lifted out of the prose flow so their
   text can't bleed into paragraphs. A scanned PDF is refused with a reason
   rather than parsing to an empty document. *Resolve* matches references to
   OpenAlex / Semantic Scholar records via a DOI → arXiv → title ladder.
2. **Read.** The paper rendered with citeproc-formatted labels in the
   detected CSL style (APA, IEEE, Chicago, Harvard, Nature vendored). Click
   any citation to jump to its bibliography entry; a structure rail moves
   between sections.
3. **Peer review.** Missing-work search across both APIs, deduped against
   your bibliography, plus claim–citation checks that fetch the cited work's
   abstract and judge whether it supports your sentence — with a verbatim
   quote, verified against the real abstract before it is shown. Every
   finding links to a real source and states its provenance, including which
   searches failed. Accepting one ("Cite this") proposes citing that exact
   source at that exact sentence.
4. **Edit.** Commands like *"add more citations to the introduction"*. The
   agent plans typed operations, searches the real APIs, and returns a
   proposal: per-section diffs, new references with sources, an integrity
   report. You approve each change; violations are unapplyable by
   construction. Sections are also editable directly, in the reader or in
   the LaTeX view.
5. **Export.** A LaTeX project zip: `main.tex`, `references.bib`, `paper.md`,
   `paper.json` (the full canonical model), and `PROVENANCE.md` (every
   agent-added source plus edit history).

## AI tools, and what I verified myself

**Where AI was used.** Built with **Claude** in an agentic coding session,
directed and reviewed by me. Claude drafted the application code — backend
pipeline, agent, API, frontend — and the tests alongside it. The architecture
(staged pipeline, citation tokens, typed agent ops, the integrity invariants)
was worked out as an explicit design conversation before and during the
coding, and is what [`docs/system-design.md`](docs/system-design.md)
documents. I did not hand-write the code line by line: I set the
requirements, made the design calls, drove the iteration, and verified the
behaviour below.

The app *also* uses an LLM at runtime — review query building, claim-support
verdicts, relevance ranking, edit planning, constrained rewrites — and never
trusts it. Quotes are checked verbatim against the real abstract before
display, citation tokens are compared as multisets before and after an edit,
and a new reference without a resolved source cannot enter the document.

**What I verified, and how:**

| | |
|---|---|
| **123 tests, no live network** | in-text detection across four style families, reference segmentation, entry parsing, the CSL round trip, the resolution ladder, the integrity checker, apply semantics, and agent flows against a scripted LLM |
| **Real papers, repeatedly** | full pipeline runs on arXiv papers with *different* citation styles, inspecting every stage's output rather than just the final result |
| **The browser, not just a clean compile** | every UI change clicked through. Several real bugs — a rail landing in the wrong grid column, a smooth scroll silently doing nothing across a long distance, a duplicate CSS rule quietly winning — typechecked perfectly and were visible only on screen |
| **A clean clone** | venv → install → tests → uvicorn → build → upload a PDF, run from a fresh `git clone` rather than the working tree |
| **The Docker image** | built, reports healthy, keys loaded from `.env` and verified *not* baked in, a real PDF parsed inside the container |
| **The failure paths, deliberately** | no LLM key (must say so, not fake it), API 429s (must become visible findings), fabricated LLM quotes (must be discarded), edits that drop a citation (must be blocked) |

**One honest caveat:** the development machine's shared egress IP exhausted
the free-tier budgets of both academic APIs during part of the work, so some
API-layer testing ran against recorded fixtures matching the real response
schemas. Live 429 behaviour — backoff, then honest failure — was exercised
for real, and nothing in the client is fixture-specific.

Full note: [`docs/ai-use-and-verification.md`](docs/ai-use-and-verification.md).

## Known limitations, and what I'd do next

In full in [`docs/limitations.md`](docs/limitations.md). The ones worth
knowing before you run it:

- **Math is lossy.** Inline math extracts as glyph soup (`∥g1:T,i∥`) and is
  preserved as text, not reconstructed. Exported `.tex` compiles as a
  structural document; a maths-heavy paper needs cleanup.
- **No OCR.** A scanned PDF is refused with a reason at stage A0 rather than
  parsing into an empty document.
- **Guarded styles stay unlinked when evidence is thin.** Superscript and
  parenthesised-numeric citations need ≥3 linked markers, because `(3)` is
  also how a paper references equation 3. Below that they stay plain text and
  the count is reported.
- **Pre-1900 years are invisible** — year detection is `19xx`/`20xx`
  throughout, which stops volume numbers being read as years but loses a
  cited 1890s work. Bites humanities papers, not contemporary STEM.
- **citeproc-py gaps:** no `<sort>`, no `suppress-author`, no `2019a/b`
  re-rendering. Worked around; a citeproc-js sidecar would fix all three.
- **Claim checks judge abstracts, not full texts** — the prompt says so, and
  returns `cannot_verify` when the abstract is insufficient.
- **Free-tier limits are real.** OpenAlex has a per-IP daily budget; from a
  shared or cloud IP it may already be spent. That surfaces as a failed
  search, never as an empty result.
- **Single process, on-disk JSON, no auth.** A local tool, not a deployment.
- **No frontend tests.** The main testing gap.

**With more time,** in the order I would do them: a **citeproc-js sidecar**
for full CSL fidelity · **benchmark the parser against GROBID** on a corpus of
arXiv PDFs with per-stage accuracy, and offer GROBID as an optional backend
for stages C–D · **richer agent ops** (move/merge paragraphs with
token-preserving splicing, replace a weak citation, deduplicate the
bibliography) · **full-text claim checking** for open-access sources, keeping
the same quote-verification rule · a **PDF-anchored view** overlaying parse
results on the original pages so extraction can be audited visually.

## Where to look

**[`docs/system-design.md`](docs/system-design.md)** is the primary document,
covering the two pieces the brief asks about, with eight diagrams:

| | |
|---|---|
| **Citation parsing** | the pipeline stage by stage with the intermediate representation between each pair of stages, where CSL-JSON sits and everything that writes into it, how the four citation-style families are detected and guarded, and where each kind of failure surfaces |
| **The agent** | how a command becomes typed operations, how the external API boundary caches / rate-limits / fails fast, how peer review runs missing-work search and claim–citation checks, and how the citation-integrity rules keep tokens conserved across an edit |

The diagrams are Mermaid, so they render on GitHub and stay diffable in
review — every one was checked against the code it describes.

Also [`docs/limitations.md`](docs/limitations.md) (known gaps and what I'd do
with more time) and
[`docs/ai-use-and-verification.md`](docs/ai-use-and-verification.md) (where AI
was used and what I checked by hand). Workflow screenshots:
[`screenshots/`](screenshots/).

```
backend/app/
  parsing/    A–E pipeline: pdf_extract → floats → structure → reflist → refparse → intext
  models/     PaperDocument (token-bearing sections), Reference (CSL-JSON canonical),
              findings, proposals, integrity reports
  external/   OpenAlex + Semantic Scholar clients, disk cache, resolution ladder
  cslproc/    citeproc rendering + vendored .csl styles
  llm/        pluggable providers (OpenAI, Gemini, mock)
  review/     claim–citation checks + missing-work search
  agent/      planner → typed ops → integrity checker → apply
  export/     LaTeX / BibTeX / Markdown / provenance
  api/        FastAPI routes; store.py = on-disk JSON persistence
backend/tests/  123 pytest tests incl. synthetic-PDF integration + float capture
frontend/       React + TS: upload → parse → read → review → edit (diff+approve) → export
Dockerfile      two stages: node builds the frontend, python runs one uvicorn over both
docker-compose.yml   one service; backend/data as a volume, backend/.env at run time
```
