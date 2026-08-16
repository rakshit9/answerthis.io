# System Design

Two pieces, as requested: **citation parsing** (how a PDF becomes parsable,
normalized citations) and **the agent** (how peer review and natural-language
editing work under the hood).

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

Two invariants hold the whole design together, and every arrow above is
arranged to protect them:

| Invariant | Enforced by |
|---|---|
| No citation is invented — every one traces to a real record | the external boundary is the *only* source of new references; integrity rule I3 rejects any that arrives without provenance |
| No edit silently breaks a citation | citations live as tokens inside the text; rules I1/I2 compare token multisets before and after, and a violating proposal cannot be applied |

---

## Piece 1 — Citation parsing

**Goal:** PDF → a structured document whose *every* citation — in-text marker
or bibliography entry — is normalized into one canonical model (CSL-JSON),
with confidence scores and explicit failure surfacing at every stage.

The pipeline is six deterministic stages (`backend/app/parsing/`). No LLM is
involved in parsing: the same PDF always parses the same way, and every
decision is explainable. The UI shows the stage log verbatim.

**The pipeline, and what each stage hands the next.** The right-hand column is
the intermediate representation — the thing that actually flows between
stages. Dashed edges are failure paths; none of them drop data silently.

```mermaid
flowchart TB
    PDF[/"PDF bytes"/] --> A0{{"A0 · readability gate"}}
    A0 -. "encrypted<br/>&lt;200 chars of text" .-> ERR["PdfExtractionError<br/>→ HTTP 422, message written for the user"]
    A0 -. "some image-only pages" .-> W0["ParseWarning: page numbers listed"]

    A0 --> A["<b>A · layout extraction</b><br/>PyMuPDF spans → lines<br/>drop rotated · strip running heads<br/>detect columns · re-join split headings"]
    A --> IRA["<code>Line{page, bbox, column,<br/>spans[{text,size,font,flags}]}</code>"]

    IRA --> AF["<b>A′ · float capture</b><br/>ruled tables → drawn boxes → image zones<br/>claim lines by centre-point"]
    AF --> IRAF["<code>FloatBlock{kind, caption, lines}</code><br/>+ prose lines, minus claimed ones"]

    IRAF --> B["<b>B · structure</b><br/>numbering · size/weight vs body font<br/>known-heading list"]
    B --> IRB["<code>Section{id, title, level, kind}</code><br/>title · abstract · section tree"]

    IRB --> C["<b>C · reference-list segmentation</b><br/>3 strategies scored, best wins"]
    C -. "no strategy scores ≥ 0.35" .-> W1["kept as one block<br/>+ reported as a segmentation failure"]
    C --> IRC["<code>RawEntry{label, raw_text,<br/>italic_segments}</code>"]

    IRC --> D["<b>D · entry parsing</b><br/>authors · year · title · venue · DOI"]
    D -. "confidence &lt; 0.5" .-> W2["kept with raw text<br/>+ flagged unparsed in the UI"]
    D --> IRD["<code>Reference{parsed, <b>csl</b>,<br/>parse_confidence, issues}</code>"]

    IRB --> E["<b>E · in-text markers</b><br/>4 style families, guarded"]
    IRD --> E
    E -. "marker links to nothing" .-> W3["left verbatim in the text<br/>+ surfaced as unlinked"]
    E --> IRE["section text with<br/><code>[[citep:ref_3]]</code> tokens"]

    IRE --> DOC[("<b>PaperDocument</b><br/>the canonical model")]
    IRD --> DOC
    IRAF --> DOC
    W0 --> REPORT[["ParseReport<br/>stage log + warnings<br/>rendered verbatim in the UI"]]
    W1 --> REPORT
    W2 --> REPORT
    W3 --> REPORT
    REPORT --> DOC

    style DOC fill:#beff50,stroke:#14140f,color:#14140f
    style ERR stroke-dasharray: 4 3
```

Every dashed edge above is a design position: the alternative to each one is
dropping data and reporting success, which is the failure mode this project
exists to avoid.

### Stage A — Layout extraction (`pdf_extract.py`)

Input: PDF file → Output: ordered, styled text lines.

0. **Readability gate.** A password-protected PDF is rejected outright. So is
   one with no text layer: the extractor counts the characters it recovered
   per page and how many pages are image-only, and if the whole document
   yields under 200 characters it raises `NoTextLayerError` naming the page
   count and pointing at OCR. Without this a scan parses "successfully" into
   0 sections and 0 references, which reads like a parser bug rather than an
   unreadable file. A PDF whose text pages are fine but which has a *few*
   image-only pages is parsed normally, with those page numbers reported as
   a warning — degrade, don't refuse.
1. `page.get_text("dict")` gives blocks → lines → spans with bounding box,
   font name, size, and style flags (bold / italic / **superscript**).
2. Rotated lines are dropped (the arXiv margin watermark), with a count in
   the parse report.
3. Repeated headers/footers: any line in the top/bottom 10% of the page whose
   digit-normalized text recurs on ≥ 35% of pages is removed, as are bare
   page numbers.
4. Column detection per page: lines are split into full-width / left / right
   by x-extent; ≥ 5 lines on each side ⇒ two-column page. Reading order is
   column-major, with full-width lines (title block, wide tables) acting as
   vertical zone separators.
5. Marker re-join: LaTeX headings often extract as two lines at the same
   height ("3.1" + "Encoder and Decoder Stacks"); a bare section-number line
   is merged with the line to its right.
6. Body font size = the mode of span sizes weighted by character count —
   the reference point for "is this line set larger/bolder than body text?"

**Intermediate representation:** `Line{page, bbox, column, spans[{text, size,
font, flags}]}` — layout and style survive to the stages that need them.

### Stage A′ — Float capture (`floats.py`)

Input: the PDF + stage-A lines → Output: figures / tables / boxed panels
lifted **out** of the prose flow.

A PDF has no "figure" or "table" object — only positioned text and vector
graphics. Without this stage, the text inside a framed definition box or
under a figure is extracted in reading order and bleeds into the
surrounding section as garbled prose, and its bold sub-headings get
mistaken for real section headings by stage B.

1. **Candidate regions** per page, in claim-priority order:
   - *ruled tables* via `page.find_tables()` (grid evidence is the
     strongest signal, so it claims first, and cells are pre-extracted as
     `a | b | c` rows);
   - *drawn boxes* — stroked/filled rects from `page.get_drawings()` big
     enough to hold text (≥ 90×24 pt) but not page-sized. A tcolorbox
     renders as an outer border rect plus an inner fill rect, so
     horizontally-aligned rects within 14 pt merge into one region;
   - *image zones* — block type 1 (raster/vector figure bodies).
2. **Claim lines** whose *center* falls inside a region (center, not
   overlap, so a line grazing a border isn't stolen). A claimed line is
   preserved on the float and removed from the prose stream — one line is
   never in both places.
3. **Captions** — lines matching `Figure N.` / `Fig. N.` / `Table N.`
   attach to the nearest region above or below within 40 pt in the same
   column band, and the caption *renames the float's kind* (a region
   detected as a generic box captioned "Figure 1." is a figure). A
   caption with no region nearby becomes a caption-only float **and a
   warning** — never silently dropped.
4. **Anchoring** — each float records the last prose line before it in
   reading order, so the pipeline attaches it to the section whose text
   surrounds it (falling back to the last section starting on/before its
   page).

**The honest contract:** nothing is dropped. Text either stays prose or
moves onto a `FloatBlock`; both are visible in the UI, and the float's
text ships in the LaTeX/Markdown export (as a `figure`/`table`
environment, or a `quote` for an uncaptioned panel). A float whose anchor
section isn't exported — e.g. it anchored into the References section —
is emitted under "Unanchored floats" rather than lost. What is *not*
reconstructed is visual layout: column structure, cell alignment, and
vector artwork are gone, and the UI says so on every float instead of
implying fidelity it doesn't have.

*Measured on the assessment's own test paper* (a 24-page ICML position
paper): captures the framed "Reasoning — informal definition / Core
positions" panel with its "Figure 1." caption and the appendix checklist
box — 66 text lines relocated out of prose, and body-section count drops
25 → 17 because the checklist's bold list headers no longer masquerade as
document sections.

### Stage B — Document structure (`structure.py`)

1. **Title** = the largest-font line block on page 1.
2. **Headings** = short lines that are (a) a known section name (Introduction,
   Methods, References, …) set apart at all (bold, larger, ALL-CAPS, or
   numbered), or (b) numbered (`3`, `3.1`, `IV.`, `A.`) *and* visually set
   apart *and* mostly alphabetic (rejects equations and list items). Level
   comes from numbering depth.
3. **Abstract** = an `Abstract` heading or an `Abstract—…` run-in.
4. Text between consecutive headings becomes a section, classified
   abstract / body / references / other.
5. Body flattening: de-hyphenation across line breaks, paragraph breaks on
   vertical gaps, and superscript numeric runs preserved as sentinels
   (`⟨sup:12,13⟩`) for stage E.

### Stage C — Reference-list segmentation (`reflist.py`)

The references section's *lines* (with layout) are segmented into entries by
three competing strategies, each returning a score; the best one wins and the
choice + score are reported:

| Strategy | Signal | Score |
|---|---|---|
| `numbered` | entries begin `[12]` / `(12)` / `12.` with near-monotonic numbers (the marker shape is whichever of the three the list actually uses) | sequence monotonicity + count |
| `hanging_indent` | entry starts at the column's left edge, continuations indented | fraction of entry-final line endings + avg length |
| `author_start` | line starts like an author list (`Surname, F.` / `F. Surname` / `Surname FM,`) and the previous line looks entry-final | fraction of entries containing a year |

Surname matching here is Unicode-aware (`textutil.UPPER_CLASS`, built once from
the Latin/Greek/Cyrillic blocks). Python's `[A-Z]` is ASCII-only, so a literal
one silently fails on `Müller` / `Álvarez` / `Öztürk` — and because
`author_start` is the fallback the other two strategies lean on, that failure
collapses an entire reference list into one unsegmented block.

If nothing scores ≥ 0.35 the list is kept as one block and **reported as a
segmentation failure** — never silently dropped. Hyphen-split words across
line breaks are re-joined; italic span runs are captured per entry as
title/venue hints.

### Stage D — Entry parsing (`refparse.py`)

Layered, deterministic field extraction; each layer removes what it matched:

1. **Identifiers** — DOI, arXiv id, URL (unambiguous regexes; a DOI is the
   strongest possible resolution key, so it is extracted first).
2. **Year** — `(2015)` (author-year styles) preferred, else a plausible
   standalone 19xx/20xx nearest the end (numbered styles). Both are
   range-guarded so `Science, 313(5786)` can't become "year 5786".
3. **Authors/title/venue split**, in order of reliability:
   - *quoted title* (IEEE): `authors "TITLE," venue`;
   - *APA anchor*: `authors (2015). title. venue`;
   - *sentence split* for dot-separated styles, with a chunker that knows
     initials (`D. P.`) don't end the author chunk **unless** the chunk
     already reads as a complete name list and the next word starts a new
     phrase (`…Salakhutdinov, R.R. Reducing the…`), and that `et al.` ends it.
4. **Author-list splitting** into `Family, Given` pairs. The genuinely
   ambiguous case — `Duchi, John, Hazan, Elad` (pairs) vs `Jimmy Lei Ba,
   Jamie Ryan Kiros` (one author per token) — is resolved by list-wide
   evidence (a comma inside the final "and"-part ⇒ pair mode; alternating
   surname-like/given-like single tokens ⇒ pair mode). Handles `&`, `;`,
   Vancouver (`Kingma DP`), particles (`van der Maaten`), and `et al.`
   (recorded as an issue, not dropped).
5. **Venue / volume / pages** from the remainder, with italic hints.
6. **Confidence** = weighted presence of authors (.3) + title (.3) +
   year (.2) + venue (.1) + identifier (.1). Entries under 0.5 are flagged
   `unparsed`: raw text kept, shown in the UI and in review findings.

**Where CSL-JSON fits:** `to_csl()` maps parsed fields into a CSL-JSON item
(`ref_N` id, csl type guessed from venue keywords, author family/given,
`issued` date-parts…). From this point on **CSL-JSON is the only citation
model in the system** — the parse metadata (confidence, issues, raw text)
lives alongside it, never instead of it. When a reference is later resolved
against OpenAlex/Semantic Scholar, its CSL-JSON is upgraded from the API
record (still under our `ref_N` id) — one model, provenance tracked.

### Stage E — In-text markers → tokens (`intext.py`)

A **probe pass** counts how many markers of each family actually *link* to
parsed reference entries:

- numeric brackets `[1, 4–7]` → via reference labels (ranges expanded,
  bounded);
- superscript runs (the stage-B sentinels) → via labels, but only trusted
  with ≥ 3 distinct linked numbers *and* no bracket style — this is the
  footnote-marker guard;
- author–year — parenthetical `(Kingma & Ba, 2015; Smith 2020a)` split on
  `;`, bracketed `[Smith et al. 2020]` (ACM and much of the humanities; a
  bracket group containing no letter is left to the numeric family), and
  narrative `Vaswani et al. (2017)` — linked by first-author family (exact,
  then fuzzy ≥ 88) + year, with `2020a/b` disambiguation by reference order.
  A group links all-or-nothing: one unlinkable part leaves the whole marker
  verbatim rather than silently dropping half of it;
- parenthesised numeric `(1)`, `(1, 3)` (PNAS, ACS, AMA) → via labels, behind
  the same kind of guard as superscripts: ≥ 3 linked markers *and* no bracket
  style present, because `(3)` is also how a paper references equation 3. When
  the guard rejects them the count is reported as a note, and the markers are
  left as plain text instead of being reported as failed citations.

The dominant family becomes the detected style (with a confidence = its share
of linked markers, shown in the UI); the tokenize pass then replaces each
**linked** marker with a canonical token in the section text:

```
[[citep:ref_1,ref_7]]   parenthetical group
[[citet:ref_3]]         narrative (author name stays in prose)
```

A marker that *looks* like a citation but doesn't link (e.g. `[42]` with no
reference 42) is left verbatim in the text and recorded as an unmatched
marker — surfaced in the parse report, never silently deleted.

**Style detection, and what happens when it is not sure.** Every family is
counted, guarded, and scored; the winner is a *reported* decision with a
confidence, not a silent one — and the user can override it.

```mermaid
flowchart TB
    TXT["section text + parsed references"] --> PROBE["probe pass —<br/>count markers of each family<br/>that actually <b>link</b> to a reference"]

    PROBE --> N1["numeric bracket<br/><code>[1, 4–7]</code>"]
    PROBE --> N2["superscript<br/><code>word¹²</code>"]
    PROBE --> N3["paren numeric<br/><code>(1, 3)</code>"]
    PROBE --> N4["author–year<br/><code>(Smith, 2020)</code> · <code>Smith (2020)</code> · <code>[Smith 2020]</code>"]

    N2 --> G1{{"≥3 linked<br/>AND no bracket style?"}}
    N3 --> G2{{"≥3 linked<br/>AND no bracket style?"}}
    G1 -. no .-> PLAIN["left as plain text<br/>+ counted in a parse note<br/><i>(footnote markers, equation refs)</i>"]
    G2 -. no .-> PLAIN

    N1 --> WIN{{"dominant family<br/>= detected style<br/>confidence = its share of linked markers"}}
    N4 --> WIN
    G1 -. yes .-> WIN
    G2 -. yes .-> WIN

    WIN --> TOK["tokenize <b>linked</b> markers<br/><code>[[citep:ref_1,ref_7]]</code> · <code>[[citet:ref_3]]</code>"]
    WIN -. "no family links anything" .-> UNKNOWN["style = unknown<br/>document still usable<br/>markers stay as written"]

    TOK --> MAP["default CSL style<br/>numeric → ieee · superscript → nature<br/>paren → ieee · author–year → apa"]
    MAP --> USER["user override —<br/>any vendored .csl"]
    USER --> CITEPROC["citeproc renders<br/>labels + bibliography"]

    UNLINK["marker that looks like a citation<br/>but resolves to nothing"] -. "never deleted" .-> KEEP["left verbatim + surfaced as unlinked"]
    PROBE --> UNLINK

    style WIN fill:#beff50,stroke:#14140f,color:#14140f
    style PLAIN stroke-dasharray: 4 3
    style UNKNOWN stroke-dasharray: 4 3
    style KEEP stroke-dasharray: 4 3
```

**Where CSL-JSON sits.** It is the *storage* format for a reference, and
citeproc is the *only* thing that turns it into text. Nothing in the app
formats a citation by hand.

```mermaid
flowchart LR
    subgraph Sources["Every way a reference can enter"]
        P["stage D — parsed from the PDF"]
        R["resolution — OpenAlex / Semantic Scholar record"]
        AG["agent search — a new work to cite"]
        RF["“Cite this” — an accepted review finding"]
    end

    P --> CSL[("<b>Reference.csl</b><br/>CSL-JSON<br/><i>single canonical shape</i>")]
    R --> CSL
    AG --> CSL
    RF --> CSL

    SEC["Section.content<br/><code>…process [[citep:ref_3]].</code>"] --> REND

    CSL --> REND["<b>citeproc-py</b> + vendored .csl"]
    REND --> L["in-text labels"]
    REND --> BIB["bibliography, ordered by the style"]
    CSL --> BIBTEX["references.bib"]
    L --> READER["reader"]
    BIB --> READER
    L --> TEX["main.tex — \\citep / \\cite"]
    BIB --> TEX

    style CSL fill:#beff50,stroke:#14140f,color:#14140f
```

A reference that cannot be rendered (too little structure, low confidence)
still appears in the bibliography with its raw text and a visible flag —
the honest fallback, rather than an entry that quietly disappears.

**Why tokens are the central design decision:** the tokens in section text
are the *source of truth* for where citations live. Everything else — the
rendered labels, the bibliography, the LaTeX `\cite` commands, the integrity
checks — is derived from them. Because they're plain text, they survive being
passed through an LLM, and because they're trivially parseable, the integrity
checker can compare the multiset of cited ids before/after any edit in one
line of code. Citation style detection maps to a default CSL style (numeric →
`ieee`, superscript → `nature`, author-year → `apa`); the user can override
with any vendored `.csl` file, and all rendering flows through citeproc.

---

## Piece 2 — The agent

Two agent surfaces share one foundation: real external search
(OpenAlex + Semantic Scholar), the canonical CSL-JSON reference table, and
the token invariant.

### The API boundary (`external/`)

- Both clients (`openalex.py`, `semantic_scholar.py`) return `ExternalSource`
  objects built **only** from API responses — a source object cannot exist
  without an api id and clickable URL, which is what makes "never hallucinate
  a reference" structural rather than aspirational.
- Every GET goes through one function (`cache.cached_get`) providing: disk
  cache (reproducible demos, kind to free tiers; failures never cached),
  client-side rate limiting (S2 unauthenticated ≈ 1 rps), 429/5xx backoff
  honoring `Retry-After`, and typed `ApiError` on definitive failure.
- Callers must handle `ApiError`; in review it becomes a visible
  `SEARCH_FAILURE` finding, in resolution a `failed` status on the reference.
  An empty result is a result; a failed call is a failure — the two are never
  conflated.

```mermaid
flowchart LR
    CALLER["review · resolution · agent search"] --> C["<b>cached_get(api, url, params)</b><br/>one door for every external call"]

    C --> HIT{{"on disk?"}}
    HIT -->|hit| RET["return — byte-identical<br/>to a live response"]
    HIT -->|miss| RL["per-API rate limiter<br/>S2: 1 req/s cumulative"]
    RL --> HTTP["HTTP GET"]

    HTTP -->|200| STORE["cache to disk"] --> RET
    HTTP -->|"429 · 5xx<br/><i>transient</i>"| BACK["bounded backoff,<br/>capped retries"] --> HTTP
    HTTP -->|"429 <i>quota exhausted</i><br/>“insufficient budget”"| FAST["fail fast — retrying<br/>cannot help"]
    HTTP -->|"4xx · timeout"| FAST

    FAST --> ERR["<b>ApiError</b><br/><i>never cached</i>"]
    ERR --> V1["review → SEARCH_FAILURE finding<br/><i>visible in the UI</i>"]
    ERR --> V2["resolution → reference marked failed"]

    style ERR stroke:#9c3b2e
    style RET fill:#beff50,stroke:#14140f,color:#14140f
```

Two distinctions in that diagram carry real weight. **A cache hit and a live
call return the same structure**, so tests run the identical code path with no
network. And **an empty result is not a failure**: a search that legitimately
found nothing says so, while a rate-limited or quota-exhausted call becomes a
finding the reviewer can see. Conflating the two would let a dead API look
like a clean bill of health — which is exactly the dishonesty this design
refuses.

### Reference resolution ladder (`external/resolve.py`)

`DOI → arXiv id → title search` (OpenAlex first, S2 as fallback), scored by
normalized-title similarity ± year/author agreement. ≥ 0.92 resolves;
0.75–0.92 is `ambiguous` (best candidate shown, not trusted); below is
`unresolved`. Resolution upgrades the reference's CSL-JSON and stores the
abstract for claim checking. Nothing is guessed: an unresolved reference
stays a parsed-but-unverified citation and is reported as such.

### Peer review (`review/`)

Runs as a background job with a live, persisted progress log (the UI shows
the raw log — including which queries ran and which failed).

```mermaid
flowchart TB
    RUN[/"user starts a review<br/>(never automatic)"/] --> SCOPE["scope: missing work? claim checks?<br/>optional section_ids"]

    SCOPE --> INTRO["<b>introspection</b> — no network<br/>unparsed refs · unresolved refs · style notes"]

    SCOPE --> MW["<b>Missing work</b>"]
    MW --> M1["M1 · build queries<br/><i>LLM: claims/topics per section</i><br/><i>no key: title + heading + keyphrases</i><br/>— provenance records which"]
    M1 --> M2["M2 · run each query on <b>both</b> APIs"]
    M2 -. "API error" .-> SF["SEARCH_FAILURE finding"]
    M2 --> M3["M3 · drop what you already cite<br/>DOI · arXiv · fuzzy title"]
    M3 --> M4["M4 · rank<br/><i>LLM relevance, else citations + overlap</i>"]
    M4 --> FMW["MISSING_WORK finding<br/>+ real ExternalSource"]

    SCOPE --> CC["<b>Claim ↔ citation checks</b>"]
    CC --> K1["K1 · claim = the sentence<br/>around the token"]
    K1 --> K2["K2 · evidence = the cited work's<br/>abstract, from resolution"]
    K2 -. "no abstract / unresolved" .-> CV["cannot_verify<br/><i>with the reason</i>"]
    K2 --> K3["K3 · one focused LLM judgment, temp 0<br/>verdict + rationale + verbatim quote"]
    K3 --> QV{{"quote actually in<br/>the abstract? (fuzzy ≥85)"}}
    QV -. no .-> DROP["quote discarded,<br/>finding says so"]
    QV -->|yes| FCC["supports · partial ·<br/>does_not_support · cannot_verify"]

    FMW --> OUT[["findings — each with its source,<br/>its section, and its provenance"]]
    FCC --> OUT
    CV --> OUT
    SF --> OUT
    INTRO --> OUT
    DROP --> OUT

    OUT --> UI["grouped in the UI:<br/>act on · checked · references · failures"]
    UI -. "“Cite this”" .-> PROPOSAL["an EditProposal citing<br/><b>that exact source</b><br/>at <b>that exact sentence</b>"]

    style OUT fill:#beff50,stroke:#14140f,color:#14140f
    style DROP stroke-dasharray: 4 3
    style SF stroke-dasharray: 4 3
```

The quote-verification step (`QV`) is the one that matters most: an LLM asked
for a supporting quote will happily produce a plausible one that is not in the
source. Checking it against the real abstract before display is the difference
between grounded review and confident fiction.

**Claim–citation checks** (`claims.py`): for a sampled set of citation sites
(spread across sections and distinct references, capped for rate limits):

1. *Claim* = the sentence containing the token (extracted at parse time).
2. *Evidence* = the cited work's abstract from resolution. No abstract ⇒ the
   finding is `cannot verify` with the reason (unresolved / no abstract /
   lookup failed) — the app never fakes a verdict.
3. *Judgment* = one focused LLM call (temperature 0) returning
   `supports / partial / does_not_support / cannot_verify` + rationale +
   a verbatim quote from the abstract. The quote is verified against the
   abstract (fuzzy ≥ 85); a fabricated quote is discarded and the finding
   says so. `does_not_support` ⇒ high severity; `partial` ⇒ medium;
   supported citations are also shown (positive findings build trust in the
   negative ones).
4. No LLM configured ⇒ every check honestly reports "needs an LLM", with the
   fetched abstract shown for manual review.

**Missing work** (`missing.py`): per body section →

1. *Query building*: LLM extracts claims/topics and search queries; without
   an LLM, keyphrase heuristics are used and the provenance string says so
   ("heuristic keyphrases (no LLM configured)") — a keyword search is never
   dressed up as a semantic one.
2. Each query runs on **both** APIs.
3. *Dedupe* against the paper's own reference list (DOI, then arXiv id, then
   fuzzy title ≥ 0.90) and against the paper itself.
4. *Ranking*: LLM relevance rating of title+abstract against the claim
   (0–3), falling back to labelled keyword-overlap + citation-count ranking.
5. Each finding carries: the claim it relates to, the section, the full
   source (title/authors/venue/year/DOI/URL/abstract), the provenance line
   (`openalex search: "..." [LLM query builder (openai:gpt-4o-mini)]`), and a
   confidence.

### Natural-language editing (`agent/`)

A command becomes a **proposal**, never a direct mutation:

```mermaid
flowchart TD
    CMD["user command<br/>'add citations to the intro'"] --> PLAN[Planner LLM →<br/>typed ops, validated]
    PLAN -->|find_citations| F[claim sites → queries →<br/>OpenAlex+S2 → dedupe → rank →<br/>new refs w/ provenance + tokens]
    PLAN -->|rewrite_section| W[constrained rewrite,<br/>token multiset verified,<br/>1 retry then hard fail]
    F --> PROP[EditProposal<br/>diffs + citation delta + step log]
    W --> PROP
    PROP --> CHECK{{Integrity checker}}
    CHECK -->|violations| BLOCK[blocked — cannot be applied]
    CHECK -->|ok| USER[per-change human approval]
    USER --> APPLY[re-check approved subset →<br/>snapshot version → apply]
```

1. **Plan.** The planner LLM maps the command onto a deliberately small,
   *typed* op vocabulary — `find_citations{section, topic, max_new}` and
   `rewrite_section{section, instruction}` — at most 4 ops, validated against
   real section ids. The LLM chooses and parameterizes operations; it does
   not get to free-form edit the document. Unmappable or destructive
   commands ("delete all references") fail with the planner's stated reason.
2. **Execute.**
   - `find_citations`: the LLM proposes claim sentences (verified to actually
     exist in the section — an invented sentence is rejected and logged) with
     search queries; both APIs are searched; candidates already in the
     bibliography are dropped; the top-ranked candidate (relevance ≥ 0.5)
     becomes a new `Reference` whose CSL comes from the API record, with
     `added_by="agent"`, the reason, and the source URL; a `[[citep:ref_N]]`
     token is inserted before the claim sentence's final period. Finding
     nothing relevant is a logged no-op, not an excuse to pad.
   - `rewrite_section`: the rewrite prompt carries hard rules (every token
     preserved byte-for-byte and count-for-count, tokens stay attached to
     their statements, no new facts). The token multiset is checked; on
     mismatch the model gets one corrective retry with the exact missing/
     invented tokens; if it still fails, **no change is produced** — the
     step log shows why.
   Every step (plan, searches with counts, drafts, checks, errors) is
   recorded in the proposal and rendered in the UI.
**How citations survive an edit.** The token is the unit that must be
conserved. Because it is plain text, it passes through an LLM unharmed;
because it is trivially parseable, conservation is a multiset comparison
rather than a heuristic.

```mermaid
flowchart TB
    BEFORE["<b>before</b><br/><code>…reasoning [[citep:ref_3]] and<br/>scaling [[citep:ref_7]].</code><br/><i>multiset {ref_3, ref_7}</i>"]

    BEFORE --> OP["operation<br/><i>rewrite_section</i> · <i>find_citations</i>"]
    OP --> RULES["hard rules in the prompt:<br/>reproduce every token byte-for-byte,<br/>keep it on the statement it supports"]
    RULES --> AFTER["<b>after</b> — candidate text"]

    AFTER --> V{{"multiset compare"}}
    V -. "token missing" .-> RETRY["one targeted retry naming<br/>the dropped tokens"]
    RETRY --> AFTER
    RETRY -. "still wrong" .-> FAIL["operation fails loudly —<br/>no partial edit is kept"]

    V -->|"⊇ before"| I1["<b>I1</b> nothing lost"]
    AFTER --> I2["<b>I2</b> every token resolves to a<br/>known or newly-proposed reference"]
    NEW["new references from search"] --> I3["<b>I3</b> each carries api + URL provenance"]
    AFTER --> I4["<b>I4</b> every declared insertion<br/>is a real token"]

    I1 --> GATE{{"IntegrityReport"}}
    I2 --> GATE
    I3 --> GATE
    I4 --> GATE

    GATE -. violation .-> BLOCK["proposal cannot be applied<br/><i>the UI has no path to force it</i>"]
    GATE -->|clean| HUMAN["per-change approval"]
    HUMAN --> SUBSET["re-check the <b>approved subset</b><br/><i>approving A but rejecting B must not leave<br/>A citing a reference only B introduced</i>"]
    SUBSET --> STALE{{"section changed<br/>since the proposal?"}}
    STALE -. yes .-> REFUSE["refuse — stale base"]
    STALE -->|no| SNAP["snapshot version → apply → recompute in-text"]
    SNAP --> DONE[("PaperDocument v+1<br/>history + provenance retained")]

    style DONE fill:#beff50,stroke:#14140f,color:#14140f
    style BLOCK stroke:#9c3b2e
    style FAIL stroke:#9c3b2e
    style REFUSE stroke:#9c3b2e
```

3. **Integrity check** (`integrity.py`) — the non-negotiable:
   - *I1 no citation lost*: per changed section, after-multiset ⊇
     before-multiset; any shortfall must be covered by an explicit,
     user-visible removal acknowledgement, else it's a blocking violation.
   - *I2 no unknown citations*: every token id must exist in the document or
     the proposal's new references.
   - *I3 real provenance*: every agent-added reference must carry a resolved
     external source (api + URL) — a citation without a source cannot enter
     the system.
   - *I4 declared adds are real*: each claimed insertion must correspond to
     an actual token.
4. **Approve & apply** (`apply.py`): the user approves per section change
   (diff view with token-aware word diff, citation counts before/after, new
   sources listed with links). Apply re-runs the integrity check on the
   approved *subset* (approving change A while rejecting change B must not
   leave A citing a reference only B introduced — unneeded new refs are
   pruned), guards against stale bases (section changed since proposal),
   snapshots the document version (undoable history), then mutates. The
   version history and every agent-added source ship in the export's
   `PROVENANCE.md`.

### Export (`export/`)

The paper rebuilds as LaTeX: tokens → `\citep`/`\citet` (natbib) for
author-year styles or `\cite` for numeric; the bibliography is a
`thebibliography` whose entry text is **rendered by citeproc with the chosen
`.csl` file** — no hand-written citation formatting anywhere (the only
non-CSL strings are natbib's `\bibitem[label]` metadata, generated from CSL
fields). `references.bib` (CSL-JSON → BibTeX), `paper.md`, canonical
`paper.json`, and `PROVENANCE.md` round out the zip. Unparsed references
appear in the bibliography with their raw text, clearly marked — they are
never dropped from the export.

---

## Key decisions & tradeoffs

- **Own parsing pipeline instead of GROBID.** GROBID would likely win on raw
  extraction quality, but it's a Java service that turns the core of this
  assessment into a black box. The staged pipeline is documented,
  deterministic, unit-tested per stage, and every failure is attributable to
  a stage. (A GROBID adapter would slot in cleanly at stages C–D if quality
  demanded it later.)
- **Tokens over offsets.** Character offsets die on every edit; inline tokens
  survive LLM round-trips and make the citation-integrity invariant a
  multiset comparison.
- **Typed agent ops over free-form editing.** A single "here's the paper,
  edit it" prompt cannot give integrity guarantees. Small ops keep each LLM
  call narrow (plan / pick claims / rate relevance / rewrite), independently
  testable, and cheap to verify.
- **citeproc-py over citeproc-js.** One-language stack; the cost is known
  CSL gaps (bibliography `<sort>` not applied — worked around by registration
  order; `suppress-author` ignored — worked around for narrative labels;
  year-suffix disambiguation incomplete). Swapping in a citeproc-js sidecar
  is isolated to `cslproc/render.py`.
- **Live APIs + disk cache.** Every response is cached on disk keyed by
  request; failures are never cached. Demos are reproducible, free-tier
  limits are respected, and the honesty rule holds: a cache hit and a live
  call are indistinguishable *except* that failures always surface.
