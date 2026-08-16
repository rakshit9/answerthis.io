# Assessment Checklist

Derived from the take-home brief. Tick each one only after verifying it in the running app / repo.

Grading weight, in the brief's own order: **1. system design → 2. code quality → 3. user interaction.**
Two things are non-negotiable regardless of that order (section 9).

## 0. Ground rules & scope

- [ ] It is a real, working web app — not a mockup, not a notebook, not CLI-only
- [ ] Frontend and backend both actually run from the documented commands
- [ ] One coherent working slice, deep — not a broad, shallow demo of everything
- [ ] Effort roughly matches the ~48h budget; scope cut where needed and cuts written down
- [ ] Not over-invested in the explicit non-goals: visual polish, exotic PDF layouts, a fully automatic human-out-of-the-loop editor
- [ ] Visual design is a free choice — but the first screen is still the upload, not a landing page

## 1. Upload & parse

- [ ] Upload a research paper PDF from the browser
- [ ] First screen is the product (upload), not a marketing landing page
- [ ] PDF → text + layout extraction step exists and is documented
- [ ] Structure extracted: title, abstract, section hierarchy
- [ ] Reference list located and segmented into individual entries
- [ ] In-text citation markers located and linked to reference entries
- [ ] Each reference entry parsed into structured fields (authors, year, title, venue, DOI…)
- [ ] More than one citation style handled (numbered/IEEE + author-year/APA at minimum)
- [ ] Style detection implemented; user can override / pick the style manually
- [ ] Unparseable citations are surfaced in the UI, never silently dropped
- [ ] Parse result visible to the user: structure + citations + references
- [ ] Pipeline is a documented algorithm with explicit stages, not ad-hoc regex that fits one file

## 2. Peer review (on request)

- [ ] Review is triggered by the user, not automatic on upload
- [ ] Missing-work search hits Semantic Scholar
- [ ] Missing-work search hits OpenAlex
- [ ] Search is driven by claim / section / topic, not just the paper title
- [ ] Claim ↔ citation matching: fetches the cited work's abstract
- [ ] Flags claims where the cited source does not actually support them
- [ ] Every finding is grounded in a real, linkable source (URL/DOI resolves)
- [ ] No hallucinated references anywhere in review output — verified on a real paper
- [ ] Findings render inline in the UI, reviewer-style and actionable
- [ ] Empty results / low-confidence matches / API failures are shown honestly
- [ ] External API boundary is clean (one client module, rate limits, caching, retries)
- [ ] Integration mode (live / cached / recorded) is a deliberate choice and stated in the docs
- [ ] OpenAlex works with no key; Semantic Scholar key is optional, app degrades gracefully without it

## 3. Agentic editing (natural language)

- [ ] User can issue free-text editing commands
- [ ] "add more citations to the introduction" works end to end
- [ ] "find me more citations that support the methodology" works end to end
- [ ] "make the intro shorter" works end to end
- [ ] Command → plan → operations pipeline (not one giant prompt doing everything)
- [ ] Existing citations survive every edit; nothing dropped silently
- [ ] Every new claim carries a real citation with its source provenance
- [ ] Citations stay attached to correct context when text moves or shrinks
- [ ] Diff / change preview shown to the user before applying
- [ ] Explicit approve (and reject) step — human stays in the loop
- [ ] Edits are targeted to what was asked — no quiet rewrite into a paper the author doesn't recognize
- [ ] Untouched sections come back byte-identical after an edit
- [ ] Export the revised paper
- [ ] LaTeX round trip preserves structure, sections, and references

## 4. CSL correctness

- [ ] Every citation — parsed or API-fetched — is stored as CSL-JSON
- [ ] CSL-JSON is the single canonical citation model (no parallel ad-hoc shape)
- [ ] Rendering/formatting goes through a citeproc library, not string templates or regex
- [ ] `.csl` style files are used for the target style (APA, IEEE, …)
- [ ] Bibliography rebuild uses the same CSL path as inline citation rendering
- [ ] Detected (or user-chosen) style actually drives the output format

## 5. Honesty & failure surfacing

- [ ] Unparseable citations visible with a reason
- [ ] Searches that return nothing say so plainly
- [ ] Low-confidence matches labeled as low confidence
- [ ] No source invented outside Semantic Scholar / OpenAlex
- [ ] Semantic vs keyword search is described accurately (no dressing up keyword search)

## 6. Code quality

- [ ] Clear module boundaries (parsing / external clients / agent / export / API / UI)
- [ ] Explicit data models for paper, section, citation, finding, edit
- [ ] Real tests on core behavior: citation parsing across styles
- [ ] Tests on citation preservation across edits
- [ ] Tests on the CSL round trip
- [ ] External API calls stubbed/recorded in tests (no live network in unit tests)
- [ ] No single mega-prompt; agent responsibilities split into distinct steps
- [ ] Tests actually run green — capture the output

## 7. System design writeup (weighted highest)

- [ ] Citation parsing doc: full pipeline stages, in order
- [ ] Citation parsing doc: intermediate representation described
- [ ] Citation parsing doc: where CSL-JSON sits in the flow
- [ ] Citation parsing doc: style handling and failure handling
- [ ] Agent doc: how a command becomes actions
- [ ] Agent doc: planning and operation execution
- [ ] Agent doc: how Semantic Scholar and OpenAlex are called
- [ ] Agent doc: how citations stay intact across edits
- [ ] Diagram(s) included
- [ ] Writeup matches what the code actually does (re-read it against the code)

## 8. Submission package

- [ ] README with run instructions verified from a clean clone
- [ ] Env/keys documented (OpenAlex keyless; S2 key optional; LLM key)
- [ ] System-design writeup included
- [ ] Screen recording or screenshots of the full workflow on a real paper
- [ ] AI-tool usage note: where AI was used, what was verified by hand
- [ ] Known limitations + "with more time" list
- [ ] Repo is clean (no stray `.DS_Store`, no large junk, no committed secrets)
- [ ] Delivered as a GitHub repo or a zip, per the brief
- [ ] Full end-to-end dry run on a fresh arXiv PDF, start to export
- [ ] Test paper's citations genuinely resolve on Semantic Scholar / OpenAlex (arXiv paper, not an obscure PDF)

## 9. Non-negotiables (final gate)

- [ ] Peer review grounded in real, linkable sources — zero hallucinated citations
- [ ] Edits never silently break the paper's citations or structure
