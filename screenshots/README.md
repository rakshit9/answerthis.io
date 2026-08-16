# Workflow screenshots

Captured **2026-08-16** against the Docker build (`docker compose up`), driving
the real app with Playwright — a real 24-page ICML position paper, a real
completed review, real sources. Nothing is mocked or staged.

| | Shows |
|---|---|
| [`01_upload.png`](01_upload.png) | First screen is the product: drop a PDF. Status pills report whether an LLM and a Semantic Scholar key are configured. |
| [`02_parse_live.png`](02_parse_live.png) | Parsing narrates the pipeline's **own** stages (A → A′ → B → C → D → E) with each stage's real result — "Extracted 2436 text lines from 24 pages" — not a decorative bar. |
| [`03_parse_overview.png`](03_parse_overview.png) | What the parser found: 24 pages, 17 sections, 152 references, 0 unparsed, 133 citations, 39 unlinked markers, 2 floats — plus the stage trace and grouped warnings. |
| [`04_reader_citations.png`](04_reader_citations.png) | The paper rendered through citeproc in the detected style, with a structure rail tagged by section kind. |
| [`05_citation_to_reference.png`](05_citation_to_reference.png) | Clicking a citation jumps to its bibliography entry and flashes it; a group citation flashes every entry it stands for. |
| [`06_review_findings.png`](06_review_findings.png) | Review findings grouped with counts (Act on / Checked / References / Failures), anchored inline under the section they concern. |
| [`07_claim_verdict.png`](07_claim_verdict.png) | A claim–citation check: the claim, the verdict with confidence, the verbatim abstract quote that justifies it, the real source, and the provenance line naming which model judged it. |
| [`08_missing_work_cite.png`](08_missing_work_cite.png) | A missing-work finding with its real source — and "Cite this", which proposes citing that exact source at that exact sentence. |
| [`09_edit_diff_integrity.png`](09_edit_diff_integrity.png) | An agent edit as a proposal: inline diff in the manuscript, `citations 4 → 6`, per-change approve, new sources with DOIs and why each was chosen, and the citation-integrity verdict on the apply bar. |
| [`10_latex_editable.png`](10_latex_editable.png) | `main.tex` regenerated live from the canonical model — click any section body and type; `\citep{…}` stays a live citation. |
| [`11_export.png`](11_export.png) | Export: style selector (auto-detected), and exactly what ships in the zip. |

Regenerate after UI changes by driving the same flow; the shots are 1600×1000
at 2× device scale.
