# Known limitations & what I'd do with more time

## Parsing

- **Math and exotic layouts.** Inline math extracted from PDFs is lossy
  (glyph soup like `∥g1:T,i∥`); the pipeline preserves it as text but doesn't
  reconstruct LaTeX math. Tables and figures are not modeled (their text can
  bleed into sections).
- **Scanned PDFs are out of scope, but not silently.** No OCR is performed.
  A PDF with no text layer is detected at stage A0 and rejected with a
  message naming the page count and suggesting `ocrmypdf`, rather than
  parsing into an empty document. A partially scanned PDF is parsed, with
  the image-only page numbers surfaced as a parse warning.
- **Heading detection** relies on numbering/size/bold heuristics plus a
  known-name list; unnumbered, body-sized headings in unusual templates can
  be missed (the text then merges into the previous section — visible in the
  outline, nothing lost).
- **Superscript citation styles** are only trusted with ≥3 distinct linked
  markers to avoid mislinking footnotes; a paper with 2 superscript citations
  won't get them linked (they're surfaced as dropped sentinels).
- **Parenthesised numeric styles** (`(1)`, `(1, 3)`) carry the same ambiguity
  against equation references, and are held to the same ≥3-marker guard plus
  the absence of a bracket style. A PNAS-style paper citing only twice keeps
  those markers as plain text, with the count reported as a parse note.
- **Citation years before 1900 are not recognised** anywhere in the pipeline —
  year detection is `19xx`/`20xx` throughout, which keeps volume and page
  numbers from being read as years but makes a cited 1890s work invisible.
  This bites historical and humanities papers, not contemporary STEM ones.
- **Author parsing** covers the common families (given-first, family-first
  pairs, initials-first, Vancouver, `et al.`, particles) but will mis-split
  rare formats; confidence + issues surface these per reference, and the raw
  string is always kept.

## CSL / rendering

- **citeproc-py gaps:** bibliography `<sort>` isn't applied by the library
  (worked around by registering items in the correct order per style family);
  `suppress-author` is ignored (narrative author-year labels are derived by
  stripping the author from the parenthetical label); year-suffix
  disambiguation (`2019a/b`) is not re-rendered by the library even though
  the parser links such markers correctly. A citeproc-js sidecar (Node) would
  fix all three and is isolated behind `cslproc/render.py`.
- **Exported LaTeX compiles as a structural document** (sections, citations,
  bibliography). Papers whose prose contains heavy extracted math may need
  manual cleanup to compile — the export is honest about being rebuilt from
  parsed text, and `paper.json` always carries the full canonical model.
- Five CSL styles are vendored; adding more is dropping a `.csl` file in
  `backend/app/cslproc/styles/`.

## External APIs

- Free-tier rate limits are real: Semantic Scholar's shared unauthenticated
  pool 429s readily (get the free `S2_API_KEY`), and OpenAlex has a daily
  request budget per IP. The app caches every response on disk, rate-limits
  itself, backs off on transient 429s, and turns definitive failures into
  visible findings — but a fully exhausted quota means "the search failed",
  honestly reported, not silently empty results.
- The client distinguishes *"slow down"* from *"your budget is spent"*: a
  transient 429 is retried with backoff (`PIA_HTTP_MAX_RETRIES`, raise it on
  the shared S2 pool), while a quota-exhausted body (e.g. OpenAlex
  "Insufficient budget") fails immediately — retrying a daily budget only
  burns wall-clock. Both end up as visible findings, but only one wastes time.
  From a shared/cloud IP (as in the recorded demo) OpenAlex's daily budget can
  already be spent by other users of that IP; from a normal machine it is not.
- Resolution quality is bounded by the APIs' coverage; ~90%+ of arXiv-paper
  references resolve, older venue-only references often stay `unresolved`
  (kept, flagged, excluded from claim checks with the reason shown).

## Agent

- The op vocabulary is deliberately small: `find_citations` and
  `rewrite_section`. No cross-section restructuring, no reference-list-only
  edits (e.g. "switch two citations"), no figure/table operations.
- One command → one proposal; proposals don't chain (apply, then issue the
  next command). Concurrent proposals on the same section are guarded by the
  stale-base check rather than merged.
- Claim checks judge against **abstracts** (what the APIs provide), not full
  texts — the verdict prompt is explicit about that limitation and returns
  `cannot_verify` when the abstract is insufficient.
- Review sampling is capped (configurable) to respect rate limits; a "check
  everything overnight" mode would just raise the caps.

## App

- Single-process, on-disk JSON store; no auth/multi-user. Fine for a local
  tool, not a deployment story.
- Undo exists as version history in the data model (and in `PROVENANCE.md`);
  there's no one-click revert button in the UI yet.

## With more time

1. **citeproc-js sidecar** for full CSL fidelity (sorting, disambiguation,
   suppress-author, locale support).
2. **Benchmark the parser** against GROBID on a corpus (e.g. 100 arXiv PDFs)
   with per-stage accuracy metrics, and add a GROBID adapter as an optional
   high-accuracy backend for stages C–D.
3. **Richer ops**: move/merge paragraphs with token-preserving splicing,
   "replace weak citation X with Y", bibliography cleanup (dedupe entries).
4. **Full-text claim checking** for open-access sources (OpenAlex OA
   locations → PDF fetch → passage retrieval), keeping the same
   quote-verification honesty rule.
5. **Embedding-based dedupe/ranking** to complement fuzzy-title matching.
6. **PDF-anchored view**: overlay parse results on the original PDF pages so
   users can audit extraction visually.
7. Streaming (SSE) for agent/review progress instead of polling.
