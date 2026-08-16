# Session handoff — Paper Improvement Agent

Snapshot of where the work stands, written so another session (or another
Claude account) can pick it up cold. Last updated **2026-08-16**.

**Read in this order:** this file for state and gotchas →
[`../README.md`](../README.md) to run it →
[`system-design.md`](system-design.md) for the architecture (the
highest-weighted deliverable) → [`limitations.md`](limitations.md) for the
roadmap → [`assessment-checklist.md`](assessment-checklist.md) for what is
actually being graded.

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

**[`../README.md`](../README.md) has the commands** and they are verified from
a clean clone (venv → pip install → tests → uvicorn → npm build → upload a
PDF). Don't duplicate them here; what follows is only what the README
deliberately leaves out.

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

**Gotchas that have each cost real time:**

- uvicorn runs without `--reload`, so *any* backend edit needs a manual
  restart. Twice I tested against stale code and got confusing results.
- The user runs **several git worktrees**, each with its own backend. Check
  `lsof -tiTCP:<port>` and verify the PID's cwd (`lsof -p <pid> | grep cwd`)
  before killing anything — port 8000 is usually a *different* worktree, and
  it may hold API keys in its process env that you cannot recreate. As of
  2026-08-16 the master worktree runs backend **:8002** and vite **:5182**
  (`PIA_BACKEND_URL=http://localhost:8002 npm run dev -- --port 5182`); the
  README's 8000/5173 are the defaults for a single checkout.
- Vite HMR resets React state, which used to lose the open paper on every
  edit. `?paper=<id>` now restores it — use that to get back into a workspace
  instead of re-uploading (which reparses and leaves duplicates).
- `docs/assessment-checklist.md` is the graded brief, itemised. Nothing in it
  is ticked yet; tick items only after verifying them in the running app.

---

## 4. Session of 2026-08-16 (most recent)

Ten commits, `97badb2` → `2ed3671`, all on `master`. Read them with
`git log --oneline 987e0e0..HEAD`; the messages carry the reasoning and are
worth reading before changing any of this. Summary:

**Parsing robustness** (`97badb2`). Stage A0 rejects an encrypted PDF and a
PDF with no text layer, with a message naming the page count and pointing at
`ocrmypdf` — before this a scan parsed "successfully" into 0 sections and 0
references, which reads as a parser bug. A partially scanned PDF still parses,
reporting the image-only page numbers. Two new in-text styles: parenthesised
numeric `(1)`, `(1, 3)` (PNAS/ACS/AMA) and bracketed author–year
`[Smith et al. 2020]` (ACM/humanities), both behind guards so equation
references don't get mistaken for citations. Unicode surnames: Python's
`[A-Z]` is ASCII-only, so Müller / Álvarez / Öztürk matched nothing — this
mattered most in stage C, where `author_start` is the fallback strategy, so
its failure collapsed a whole reference list into one block.

**Merge of `design/perk-lime`** (`9186034`). Both branches sat on the same
commit with disjoint uncommitted work. Brought in the live parse view
(upload returns immediately, parsing runs in a thread, the client polls the
pipeline's real stages) and the editable LaTeX view.

**Reader** (`c065911`, `bac01d8`). A structure rail mirroring the LaTeX
outline, each entry tagged with its parsed section kind. Citations became
clickable: `render_paragraphs()` returns the same text as `render_text()` but
keeps each label joined to its ref ids, so the frontend can link a label to
its bibliography entry without a second citation renderer. Clicking flashes
the entry; "Back to the text" returns.

**Editing** (`e0663d3`). The LaTeX body is the click target — click the line
you want and type. ⌘⏎ saves, Esc cancels. Round-tripped both directions on a
real paper with citations intact.

**Review → citation** (`ff0af19`). "Cite this" on a missing-work finding
proposes citing *that exact source* at *that exact sentence*, through the same
proposal → integrity → approve path as an agent edit. No LLM involved, so it
works with no key. `reference_from_source()` is now shared with the agent's
own search so both build identically shaped, provenance-carrying references.
It refuses rather than guesses: already-cited works and findings whose anchor
sentence has changed are rejected with a reason.

**Panels and shell** (`2bab19a`, `0b44c42`, `5d2a607`, `92f2386`). Findings
group into Act on / Checked / References / Failures with counts, sort by
severity, and identical repeats collapse to one card with ×N (a dead API was
producing ten identical cards). Spacing was fixed at the root — every block
had set its own margins, and a duplicate `.checkrow` rule was silently
winning. `?paper=<id>` routing plus a paper switcher in the breadcrumb;
before this, a parsed paper was reachable only by uploading its PDF again.

**Config** (`e0663d3`). `config.py` reads `backend/.env` via a small
dependency-free loader. Exported vars still win.

---

## 5. Earlier session — stage A′ and the UI rebuild

### Stage A′ — float capture (figures / tables / boxed panels)

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

### Export bug fixed (was a contract violation)

Export ignored floats entirely → float text vanished from the LaTeX round
trip. Fixed by emitting `figure`/`table` environments (and `quote` for
uncaptioned panels).

Then a subtler case surfaced: a float can anchor to the **References**
section, which the exporter skips — so it was *still* being silently dropped.
Now any float not emitted in-section ships under `\section*{Unanchored
floats}`. Same fix applied to the Markdown export. Regression test:
`test_float_anchored_to_skipped_section_still_exports`.

### UI rebuilt around the manuscript

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

## 6. Verification state

- **116 backend tests pass** (`cd backend && .venv/bin/python -m pytest
  tests/`), up from 76. No live network in them — the one test that touches
  `httpx` monkeypatches it.
- Frontend `npx tsc -b` clean, `npm run build` clean.
- **Verified from a clean `git clone`** on 2026-08-16, not just the working
  tree: venv → pip install → 116 pass → `cp .env.example .env` → uvicorn
  starts and reports `llm: null` honestly with no keys → `npm run build` →
  uvicorn serves that build at `/` → uploading a PDF parses to 21 sections /
  152 references. The clone contained `.env.example` and no `.env`.
- No frontend tests exist (still true; the main testing gap).
- Every UI change this session was checked in a real browser — clicking
  through, not just compiling. Worth continuing: several bugs (the reader
  outline landing in the wrong grid column, a smooth scroll silently doing
  nothing across a long distance, a duplicate CSS rule winning) typechecked
  perfectly and were only visible on screen.

**Useful stored data** (in `backend/data/<paper_id>/`, gitignored):
- `67dd7ed05a97` — the 24-page ICML position paper with a **completed review
  run**: 40 findings, 8 of them missing-work with real sources. Good for
  demoing review and "Cite this" without burning API calls. Open it directly
  at `http://localhost:5182/?paper=67dd7ed05a97`.
- `812293d7cd53` — the same paper, parsed with floats.

⚠️ `backend/data/` currently holds **~53 papers**, most of them repeat test
uploads of that same PDF from 2026-08-16. Harmless and gitignored, but worth
pruning before recording a demo — the paper switcher lists all of them. Ask
the user before deleting; some carry review runs and proposals.

Papers parsed before A′ existed will show 0 floats — re-upload to refresh.

---

## 7. Known limitations / what’s next

Check [`limitations.md`](limitations.md) fresh — it is the roadmap source of
truth. Live issues as of this session:

- **Math notation is lossy.** PDFs encode math as positioned glyphs, so
  `→ Σ*` extracts as `→Σ∗` and diacritics split (`Gonz´alez`, `H¨uy-uk` —
  these also cause some of the 39 unlinked in-text markers). Documented, not
  fixed. Not flagged inline in the UI on affected sections — a proposed but
  unbuilt improvement.
- ⚠️ **OpenAlex is returning `HTTP 429 / Insufficient budget` on every call**
  ("this request costs $0.001 but you only have $0 remaining"). As of
  2026-08-16 that is *persistent*, not a daily blip: missing-work search is
  effectively running on Semantic Scholar alone, and each review produces ~10
  `search_failure` findings. The app handles it correctly — it refuses to let
  a dead API look like "nothing found" — but the brief asks for both APIs, so
  **resolve this before recording a demo**. Nothing in the code needs fixing;
  it is the OpenAlex account/IP.
- **Section-scoped review is not wired into the UI.** The backend already
  honours `scope.section_ids` (`review/engine.py`); the panel only sends the
  two checkboxes, so every run covers the whole paper and spreads a 10-query
  budget across 17 sections. Small, worthwhile, not done.
- **No raw-PDF viewer.** The Read/Paper view shows reflowed extracted text,
  not PDF pixels. The user has asked about a two-pane "real PDF + select text
  → explain/edit" flow (like AnswerThis). That needs: `pdf.js` on the
  frontend, a backend endpoint to serve stored PDF bytes, and a new read-only
  "explain selection" endpoint. **Not started.**
- No frontend tests. No auth, no DB (on-disk JSON), single process.

---

## 8. Ways of working the user has confirmed

- On broad asks ("revamp this"), **propose a concrete ordered plan** rather
  than asking them to pick from options up front — they want to be driven.
- When they paste a detailed UI spec, implement it **literally**, isolate it
  behind a new route rather than mutating existing screens, wire it to real
  endpoints, and say plainly which parts are real vs. placeholder.
- Verify in an actual browser before reporting done — they care about
  interaction fidelity, not just a clean compile.
- Prefer honest failure over fake success everywhere; it is this project's
  whole thesis.
- They ask short, telegraphic questions ("why new citation are not added",
  "look ugly improve the space") and expect you to find the real cause rather
  than patch the symptom. Twice this session the stated complaint had a
  structural cause — findings were unreachable because review is read-only by
  design, and the spacing was broken because every block set its own margins
  plus a duplicate CSS rule. Say what the actual cause was.
- Don't ask which of several options they want on something with an obvious
  default; pick, do it, and say what you picked and why.
- Flag anything you did beyond the literal ask (this session: `?paper=`
  routing while fixing spacing) rather than slipping it in silently.
- Uncommitted work makes them nervous — commit each coherent piece as it
  lands, with a message explaining *why*, not just what.
