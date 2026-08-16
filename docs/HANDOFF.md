# Session handoff — Paper Improvement Agent

Snapshot of where the work stands, written so another session (or another
Claude account) can pick it up cold. Last updated **2026-08-15**.

---

## 1. What this project is

Upload a research-paper PDF → inspect the parse → get a peer review grounded
in **real** academic search (Semantic Scholar + OpenAlex) → edit by
natural-language command → export as LaTeX. Citations are canonical
**CSL-JSON** end to end, rendered by citeproc, protected by a
citation-integrity checker.

Built as a timed take-home assessment. The graded priorities, in order:
**system design → code quality → user interaction**, with two
non-negotiables: peer review must be grounded in real linkable sources
(never hallucinated), and edits must never silently break citations or
structure.

Read [`system-design.md`](system-design.md) first — it is the primary
deliverable. Then [`limitations.md`](limitations.md) for the roadmap.

---

## 2. Status

All of the work described below is **committed on `master`** (it was
uncommitted when this note was first written on 2026-08-15; it landed on
2026-08-16, along with the design-branch UI work, which was merged in).
Nothing has been pushed to a remote.

For how to run the app, read [`../README.md`](../README.md) — it is verified
from a clean clone and is the authority. The rest of this file is background
on how the code got the shape it has.

---

## 3. How to run

```bash
# backend (from backend/)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
OPENAI_API_KEY=… S2_API_KEY=… uvicorn app.main:app --port 8000
```

```bash
# frontend (from frontend/)
npm install && npm run dev        # proxies /api → :8000
```

**Keys** (values are NOT stored in this repo or any doc — get them from the
user):
- `OPENAI_API_KEY` — enables claim verdicts + agentic editing. Without it the
  app degrades *honestly* rather than faking output.
- `S2_API_KEY` — Semantic Scholar. Free. Rate limit is **1 req/sec
  cumulative**, which is strict; the agent paces against it.
- OpenAlex needs no key. `OPENALEX_MAILTO` is just an email for the polite pool.

Put them in `backend/.env` (gitignored; `.env.example` lists the keys) —
`config.py` loads that file at startup. An exported shell variable still
overrides the file. *This changed on 2026-08-16; before that the backend read
plain `os.environ` only and a `.env` file silently did nothing.*

Verify with `curl localhost:8000/api/health` → should show
`{"llm":"openai:gpt-4o-mini",…,"semantic_scholar_key":true}`. That only proves
a key is present, not that it has quota — curl the provider directly to catch
billing errors.

**Gotcha that cost time this session:** uvicorn runs without `--reload`, so
*any* backend edit needs a manual restart. Twice I tested against stale code
and got confusing results. Also check `lsof -tiTCP:8000` — the user runs
multiple worktrees, and another worktree's backend may hold the port. Verify
the PID's cwd (`lsof -p <pid> | grep cwd`) before killing anything.

---

## 4. What changed this session

### 4a. Stage A′ — float capture (figures / tables / boxed panels)

The headline change. New file `backend/app/parsing/floats.py`; pipeline is now
`A → A′ → B → C → D → E`.

**Problem it solves:** a PDF has no "figure" or "table" object, only
positioned text and graphics. Text inside a framed panel was bleeding into
section prose as garbled text, *and* its bold sub-headings were being
mistaken for real document headings by stage B.

**Approach** — deterministic, layout-evidence based, in claim-priority order:
ruled tables (`find_tables()`, strongest evidence, claims first) → drawn boxes
(`get_drawings()`, with border+fill rect merging for tcolorbox) → image zones.
Lines are claimed by **center-point** containment. Captions attach within 40pt
and *rename* the float's kind. Orphan captions become caption-only floats plus
a surfaced warning.

**Measured on the real test paper** (24-page ICML position paper, stored as
paper `812293d7cd53`): captures the "Reasoning — informal definition / Core
positions" panel with its `Figure 1.` caption, plus the appendix checklist
box. 66 text lines relocated out of prose. **Body sections dropped 25 → 17**
because the checklist's list headers stopped masquerading as sections.

**Contract:** nothing is dropped — text is either prose or on a `FloatBlock`,
both visible in the UI and both shipped in exports. Visual layout is *not*
reconstructed, and the UI says so on every float rather than implying
fidelity it doesn't have.

Note: `floats.py` + `test_floats.py` + the `core.py`/`pipeline.py` edits came
from an *earlier* session and were found already on disk; this session
verified them, then completed the export path and the frontend.

### 4b. Export bug fixed (was a contract violation)

Export ignored floats entirely → float text vanished from the LaTeX round
trip. Fixed by emitting `figure`/`table` environments (and `quote` for
uncaptioned panels).

Then a subtler case surfaced: a float can anchor to the **References**
section, which the exporter skips — so it was *still* being silently dropped.
Now any float not emitted in-section ships under `\section*{Unanchored
floats}`. Same fix applied to the Markdown export. Regression test:
`test_float_anchored_to_skipped_section_still_exports`.

### 4c. UI rebuilt around the manuscript

Nav collapsed 5 stepped tabs → **3**: `Parse → Paper (review & edit) → Export`.

New `frontend/src/components/Workspace.tsx` — a split view replacing the old
separate Read/Review/Edit screens (those three files were **deleted**):
- **Left:** the manuscript as a clean sheet with citeproc-rendered citations.
  Review findings anchor **inline under the section they concern** as colored
  chips. Proposed edits render as **in-place diffs inside the paper** with
  per-change approve checkboxes. Sticky bottom bar carries the integrity
  verdict + Apply/Reject.
- **Right:** slim panel, tabs for Peer review (run button, live progress log,
  finding cards with linked sources, `↦ section` jump links that scroll +
  flash) and Edit (command box, agent step log, new sources, history).

New `frontend/src/components/LatexPane.tsx` — a **Paper | LaTeX** toggle. The
LaTeX view shows real `main.tex` regenerated live from the canonical model,
with a clickable structure outline, syntax highlighting, `\citep{…}` as chips,
and it refetches on `paper.version` change — so an applied edit is immediately
visible in the source.

Parse view also got: warnings grouped into collapsible per-stage `<details>`
(39 raw orange lines were unreadable), a scroll-capped sticky-header reference
table, and a floats stat card + expandable float list.

---

## 5. Verification state

- **76 backend tests pass** (`cd backend && python -m pytest tests/`), up from
  67. New: 6 float-parsing + 3 export-contract tests.
- Frontend `npx tsc -b` clean, `npm run build` clean.
- No frontend tests exist (still true; a known gap).
- UI verified in a real browser, not just typecheck.

**Useful stored data** (in `backend/data/<paper_id>/`):
- `812293d7cd53` — the test paper **re-parsed with floats**. Use this one.
- `e2b98d3be3da` — same PDF parsed *before* A′ existed, so `floats: []`. It
  has a completed review run with **56 real findings** and 2 edit proposals
  (one pending, "add more citations to the introduction", 3 real sources
  attached). Good for demoing review/edit without burning API calls.

Papers parsed before A′ existed will show 0 floats — re-upload to refresh.

---

## 6. Known limitations / what's next

Check [`limitations.md`](limitations.md) fresh — it is the roadmap source of
truth. Live issues as of this session:

- **Math notation is lossy.** PDFs encode math as positioned glyphs, so
  `→ Σ*` extracts as `→Σ∗` and diacritics split (`Gonz´alez`, `H¨uy-uk` —
  these also cause some of the 39 unlinked in-text markers). Documented, not
  fixed. Not flagged inline in the UI on affected sections — a proposed but
  unbuilt improvement.
- **OpenAlex daily budget** for this IP got exhausted during testing
  (`HTTP 429 / Insufficient budget`). Surfaced honestly in the progress log;
  resets daily.
- **No raw-PDF viewer.** The Read/Paper view shows reflowed extracted text,
  not PDF pixels. The user has asked about a two-pane "real PDF + select text
  → explain/edit" flow (like AnswerThis). That needs: `pdf.js` on the
  frontend, a backend endpoint to serve stored PDF bytes, and a new read-only
  "explain selection" endpoint. **Not started.**
- No frontend tests. No auth, no DB (on-disk JSON), single process.

---

## 7. Ways of working the user has confirmed

- On broad asks ("revamp this"), **propose a concrete ordered plan** rather
  than asking them to pick from options up front — they want to be driven.
- When they paste a detailed UI spec, implement it **literally**, isolate it
  behind a new route rather than mutating existing screens, wire it to real
  endpoints, and say plainly which parts are real vs. placeholder.
- Verify in an actual browser before reporting done — they care about
  interaction fidelity, not just a clean compile.
- Prefer honest failure over fake success everywhere; it is this project's
  whole thesis.
