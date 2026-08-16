// Mirrors backend/app/models — the shapes the API returns.

export interface ParseWarning { stage: string; message: string; detail?: string | null }

export interface ParseReport {
  stages: string[];
  warnings: ParseWarning[];
  n_pages: number;
  n_references_found: number;
  n_references_parsed: number;
  n_references_unparsed: number;
  n_intext_citations: number;
  n_intext_unmatched: number;
  n_floats: number;
  intext_style: string;
  intext_style_confidence: number;
}

export interface ParsedFields {
  authors: string[]; year?: number | null; title?: string | null;
  container?: string | null; doi?: string | null; arxiv_id?: string | null;
  url?: string | null; pages?: string | null; volume?: string | null;
}

export interface Resolution {
  status: string; source?: string | null; source_id?: string | null;
  source_url?: string | null; doi?: string | null; match_score?: number | null;
  method?: string | null; error?: string | null; abstract?: string | null;
}

export interface Reference {
  id: string; raw_text: string; label?: string | null;
  parsed: ParsedFields; parse_confidence: number; parse_issues: string[];
  csl: Record<string, unknown>; resolution: Resolution;
  added_by: string; added_reason?: string | null;
}

export interface Section {
  id: string; title: string; level: number; kind: string; content: string;
  page_start?: number | null; page_end?: number | null;
}

/** A figure, table, or boxed panel captured out of the prose flow (stage A′).
 *  Text is preserved; visual layout is not reconstructed. */
export interface FloatBlock {
  id: string; kind: "figure" | "table" | "box";
  caption: string; text: string; page: number;
  section_id?: string | null;
}

export interface InTextCitation {
  section_id: string; raw: string; ref_ids: string[]; context: string;
}

export interface Paper {
  id: string; filename: string; uploaded_at: number;
  meta: { title: string; authors: string[]; abstract: string };
  sections: Section[]; floats: FloatBlock[]; references: Reference[];
  intext_citations: InTextCitation[];
  parse_report: ParseReport;
  csl_style: string; csl_style_detected: boolean;
  version: number;
  history: { version: number; reason: string; created_at: number }[];
}

export interface ExternalSource {
  api: string; api_id: string; title: string; year?: number | null;
  authors: string[]; venue?: string | null; doi?: string | null;
  url: string; abstract?: string | null; cited_by_count?: number | null;
}

export interface Finding {
  id: string; type: string; severity: string; title: string; detail: string;
  section_id?: string | null; section_title?: string | null;
  claim_text?: string | null; ref_ids: string[];
  verdict?: string | null; verdict_rationale?: string | null;
  evidence_quote?: string | null; source?: ExternalSource | null;
  provenance?: string | null; confidence?: number | null; llm_used?: string | null;
}

export interface ReviewRun {
  id: string; paper_id: string; status: string; progress: string[];
  findings: Finding[]; error?: string | null; started_at: number;
}

export interface SectionChange {
  id: string; section_id: string; section_title: string;
  before: string; after: string; rationale: string;
  citations_before: string[]; citations_after: string[];
  approved?: boolean | null;
}

export interface IntegrityViolation {
  kind: string; message: string; section_id?: string | null; ref_ids: string[];
}

export interface IntegrityReport {
  ok: boolean; violations: IntegrityViolation[]; warnings: IntegrityViolation[];
  summary: string;
}

export interface AgentStep { t: number; kind: string; text: string; data: Record<string, unknown> }

export interface CitationAdd { ref_id: string; reason: string; api: string; source_url: string; anchor_text?: string | null }

export interface EditProposal {
  id: string; paper_id: string; command: string; status: string; plan: string;
  steps: AgentStep[]; changes: SectionChange[];
  new_references: Reference[]; citation_adds: CitationAdd[];
  citation_removals: { ref_id: string; section_id: string; reason: string }[];
  integrity: IntegrityReport; error?: string | null; llm_used?: string | null;
  created_at: number;
}

/** One piece of rendered prose: either plain text, or a citation label with
 *  the references it stands for. */
export type CitePart = { t?: string; label?: string; refs?: string[] };

export interface RenderedDoc {
  style: string;
  sections: {
    id: string; title: string; level: number; kind: string;
    html: string;
    /** Same text as `html`, split into paragraphs of parts, with each
     *  citation label still carrying the ref ids it stands for. */
    paragraphs?: CitePart[][];
  }[];
  bibliography: { ref_id: string; formatted: string; raw_fallback: boolean }[];
}

/** Live progress of the parse pipeline — one event per completed stage. */
export interface ParseStageInfo { key: string; label: string }
export interface ParseEvent { key: string; text: string; t: number }
export interface ParseJob {
  status: "running" | "done" | "failed";
  current: string | null;
  events: ParseEvent[];
  stages: ParseStageInfo[];
  filename?: string;
  error?: string | null;
}

export interface Health { llm: string | null; llm_hint: string | null; semantic_scholar_key: boolean }
export interface StyleInfo {
  id: string;
  title: string;
  author_year?: boolean;
  /** "author–date" | "numeric" — how in-text citations are formed. */
  family?: string;
  in_text?: string;
  bibliography?: string;
  /** What switching to this style changes in the exported paper. */
  changes?: string[];
}

/** One style rendered against this paper's own first cited references. */
export interface StyleSample {
  parenthetical?: string;
  narrative?: string;
  group?: string | null;
  bibliography?: string[];
  error?: string;
}
