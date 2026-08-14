import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Finding, Paper, ReviewRun } from "../types";
import { Badge, SourceLine } from "./bits";

const VERDICT_LABEL: Record<string, string> = {
  supports: "✓ supports",
  partial: "◐ partial support",
  does_not_support: "✗ does not support",
  cannot_verify: "? cannot verify",
};

function FindingCard({ f }: { f: Finding }) {
  return (
    <div className={`card finding ${f.severity}`}>
      <div className="ftitle">
        <Badge tone={f.severity === "high" ? "bad" : f.severity === "medium" ? "warn" : f.severity === "info" ? "good" : ""}>
          {f.type.replace(/_/g, " ")}
        </Badge>
        {f.title}
      </div>
      {f.section_title && <div className="small muted">in section: {f.section_title}</div>}
      {f.claim_text && (
        <blockquote>“{f.claim_text}”</blockquote>
      )}
      {f.verdict && (
        <div className="small">
          <strong>{VERDICT_LABEL[f.verdict] ?? f.verdict}</strong>
          {typeof f.confidence === "number" ? ` (confidence ${f.confidence})` : ""}
          {f.verdict_rationale ? ` — ${f.verdict_rationale}` : ""}
        </div>
      )}
      {!f.verdict && f.detail && <div className="small">{f.detail}</div>}
      {f.evidence_quote && (
        <blockquote className="small">Abstract says: “{f.evidence_quote}”</blockquote>
      )}
      {f.source && <SourceLine s={f.source} />}
      {f.provenance && (
        <div className="prov">
          provenance: {f.provenance}
          {f.llm_used && !f.provenance.includes(f.llm_used) ? ` · judged by ${f.llm_used}` : ""}
        </div>
      )}
    </div>
  );
}

export function ReviewView({ paper, llm }: { paper: Paper; llm: string | null }) {
  const [runs, setRuns] = useState<ReviewRun[]>([]);
  const [active, setActive] = useState<ReviewRun | null>(null);
  const [missingWork, setMissingWork] = useState(true);
  const [claimChecks, setClaimChecks] = useState(true);
  const [starting, setStarting] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    api.reviews(paper.id).then((rs) => {
      setRuns(rs);
      if (rs.length && !active) setActive(rs[0]);
      if (rs.length && (rs[0].status === "running" || rs[0].status === "pending")) poll(rs[0].id);
    }).catch(() => {});
    return () => { if (timer.current) window.clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper.id]);

  const poll = (runId: string) => {
    api.review(paper.id, runId).then((r) => {
      setActive(r);
      setRuns((rs) => [r, ...rs.filter((x) => x.id !== r.id)]);
      if (r.status === "running" || r.status === "pending") {
        timer.current = window.setTimeout(() => poll(runId), 1500);
      }
    }).catch(() => {});
  };

  const start = async () => {
    setStarting(true);
    try {
      const { run_id } = await api.startReview(paper.id, {
        missing_work: missingWork, claim_checks: claimChecks,
      });
      poll(run_id);
    } finally { setStarting(false); }
  };

  const running = active != null && (active.status === "running" || active.status === "pending");
  const findings = (active?.findings ?? []).filter(
    (f) => typeFilter === "all" || f.type === typeFilter);
  const types = Array.from(new Set((active?.findings ?? []).map((f) => f.type)));

  return (
    <div>
      {!llm && (
        <div className="notice">
          No LLM provider configured — claim–citation verdicts and semantic query
          building are disabled. Reference resolution, abstract fetching, and
          keyword-based missing-work search still run, and everything they can't
          do is reported as “cannot verify”, not guessed.
        </div>
      )}
      <div className="card">
        <div className="runbar">
          <button className="primary" onClick={() => void start()} disabled={running || starting}>
            {running ? "Review running…" : "Run peer review"}
          </button>
          <label className="checklabel">
            <input type="checkbox" checked={missingWork} onChange={(e) => setMissingWork(e.target.checked)} />
            missing work (search both APIs)
          </label>
          <label className="checklabel">
            <input type="checkbox" checked={claimChecks} onChange={(e) => setClaimChecks(e.target.checked)} />
            claim–citation checks
          </label>
          {runs.length > 1 && (
            <select value={active?.id ?? ""} onChange={(e) => {
              const r = runs.find((x) => x.id === e.target.value);
              if (r) setActive(r);
            }}>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {new Date(r.started_at * 1000).toLocaleTimeString()} — {r.status} ({r.findings.length})
                </option>
              ))}
            </select>
          )}
        </div>
        {active && (
          <div style={{ marginTop: 12 }}>
            <div className="progress-log">
              {active.progress.map((p, i) => <div key={i}>{p}</div>)}
              {running && <div><span className="spin" /> working…</div>}
            </div>
            {active.error && <div className="error-banner" style={{ marginTop: 10 }}>{active.error}</div>}
          </div>
        )}
      </div>

      {active && active.findings.length > 0 && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "16px 0 10px" }}>
            <h3 style={{ margin: 0 }}>Findings ({findings.length})</h3>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="all">all types</option>
              {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          {findings.map((f) => <FindingCard key={f.id} f={f} />)}
        </>
      )}
      {active && active.status === "done" && active.findings.length === 0 && (
        <div className="card">The review finished without findings.</div>
      )}
    </div>
  );
}
