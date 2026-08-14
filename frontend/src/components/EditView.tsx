import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { EditProposal, Paper, Reference } from "../types";
import { Badge, SourceLine } from "./bits";
import { DiffView } from "./diff";

const EXAMPLES = [
  "add more citations to the introduction",
  "find me more citations that support the methodology",
  "make the introduction shorter",
  "tighten the conclusion without losing any citations",
];

export function EditView({ paper, llm, onApplied }: {
  paper: Paper; llm: string | null; onApplied: () => void;
}) {
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [prop, setProp] = useState<EditProposal | null>(null);
  const [proposals, setProposals] = useState<EditProposal[]>([]);
  const [approved, setApproved] = useState<Record<string, boolean>>({});
  const [applyError, setApplyError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    api.proposals(paper.id).then((ps) => {
      setProposals(ps);
      const open = ps.find((p) => p.status === "running" || p.status === "proposed");
      if (open) { setProp(open); seedApprovals(open); if (open.status === "running") poll(open.id); }
    }).catch(() => {});
    return () => { if (timer.current) window.clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper.id]);

  const refsMap = useMemo(() => {
    const m = new Map<string, Reference>();
    paper.references.forEach((r) => m.set(r.id, r));
    prop?.new_references.forEach((r) => m.set(r.id, r));
    return m;
  }, [paper, prop]);

  const seedApprovals = (p: EditProposal) => {
    const a: Record<string, boolean> = {};
    p.changes.forEach((c) => { a[c.id] = p.integrity.ok; });
    setApproved(a);
  };

  const poll = (propId: string) => {
    api.proposal(paper.id, propId).then((p) => {
      setProp(p);
      setProposals((ps) => [p, ...ps.filter((x) => x.id !== p.id)]);
      if (p.status === "running") timer.current = window.setTimeout(() => poll(propId), 1500);
      else seedApprovals(p);
    }).catch(() => {});
  };

  const run = async () => {
    if (!command.trim()) return;
    setBusy(true); setApplyError(null);
    try {
      const { proposal_id } = await api.startEdit(paper.id, command.trim());
      poll(proposal_id);
    } catch (e) {
      setApplyError(String(e instanceof Error ? e.message : e));
    } finally { setBusy(false); }
  };

  const apply = async () => {
    if (!prop) return;
    setApplyError(null);
    const ids = Object.entries(approved).filter(([, v]) => v).map(([k]) => k);
    try {
      await api.applyProposal(paper.id, prop.id, ids);
      onApplied();
      poll(prop.id);
    } catch (e) {
      setApplyError(String(e instanceof Error ? e.message : e));
    }
  };

  const reject = async () => {
    if (!prop) return;
    await api.rejectProposal(paper.id, prop.id);
    poll(prop.id);
  };

  const running = prop?.status === "running";

  return (
    <div>
      {!llm && (
        <div className="notice">
          Agentic editing requires an LLM provider (OPENAI_API_KEY or
          GEMINI_API_KEY). Commands will fail honestly until one is configured.
        </div>
      )}
      <div className="card">
        <div className="cmd">
          <input
            value={command}
            placeholder='Tell the agent what to improve — e.g. "add more citations to the introduction"'
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void run(); }}
          />
          <button className="primary" onClick={() => void run()} disabled={busy || running}>
            {running ? "Agent working…" : "Propose edit"}
          </button>
        </div>
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button key={ex} onClick={() => setCommand(ex)}>{ex}</button>
          ))}
        </div>
      </div>

      {applyError && <div className="error-banner">{applyError}</div>}

      {prop && (
        <div className="card">
          <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
            <h3 style={{ margin: 0 }}>“{prop.command}”</h3>
            <Badge tone={prop.status === "applied" ? "good" : prop.status === "failed" ? "bad" : prop.status === "proposed" ? "accent" : ""}>
              {prop.status}
            </Badge>
            {prop.llm_used && <span className="small muted">agent: {prop.llm_used}</span>}
            {proposals.length > 1 && (
              <select style={{ marginLeft: "auto" }} value={prop.id} onChange={(e) => {
                const p = proposals.find((x) => x.id === e.target.value);
                if (p) { setProp(p); seedApprovals(p); }
              }}>
                {proposals.map((p) => (
                  <option key={p.id} value={p.id}>“{p.command.slice(0, 44)}” — {p.status}</option>
                ))}
              </select>
            )}
          </div>

          {prop.plan && <p className="small" style={{ marginBottom: 4 }}><strong>Plan:</strong> {prop.plan}</p>}

          {prop.steps.length > 0 && (
            <ul className="step-log">
              {prop.steps.map((s, i) => (
                <li key={i}><span className="k">{s.kind}</span>{s.text}</li>
              ))}
              {running && <li><span className="spin" /> …</li>}
            </ul>
          )}

          {prop.error && <div className="error-banner">{prop.error}</div>}

          {prop.status !== "running" && prop.changes.length > 0 && (
            <>
              <div className={`integrity ${prop.integrity.ok ? "ok" : "fail"}`}>
                <strong>Citation integrity:</strong> {prop.integrity.summary}
                {prop.integrity.violations.map((v, i) => (
                  <div key={i}>✗ {v.message}</div>
                ))}
                {prop.integrity.warnings.map((v, i) => (
                  <div key={`w${i}`}>⚠ {v.message}</div>
                ))}
              </div>

              {prop.new_references.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <h3>New references the agent wants to add ({prop.new_references.length})</h3>
                  {prop.citation_adds.map((a) => {
                    const r = prop.new_references.find((x) => x.id === a.ref_id);
                    return (
                      <div key={a.ref_id} className="card" style={{ marginBottom: 8 }}>
                        {r && r.resolution.source_url && (
                          <SourceLine s={{
                            api: a.api, api_id: r.resolution.source_id ?? "",
                            title: String(r.csl.title ?? r.parsed.title ?? "?"),
                            year: r.parsed.year ?? null, authors: r.parsed.authors,
                            venue: r.parsed.container ?? null, doi: r.resolution.doi ?? null,
                            url: a.source_url, abstract: r.resolution.abstract ?? null,
                            cited_by_count: null,
                          }} />
                        )}
                        <div className="small muted">why: {a.reason}</div>
                        {a.anchor_text && <div className="small muted">anchored to: “{a.anchor_text}”</div>}
                      </div>
                    );
                  })}
                </div>
              )}

              <div style={{ marginTop: 12 }}>
                <h3>Proposed changes — approve each one</h3>
                {prop.changes.map((c) => (
                  <div key={c.id} className="card">
                    <div className="change-head">
                      <strong>{c.section_title}</strong>
                      <span className="small muted">
                        citations: {c.citations_before.length} → {c.citations_after.length}
                      </span>
                      {prop.status === "proposed" && (
                        <label>
                          <input type="checkbox" checked={approved[c.id] ?? false}
                            onChange={(e) => setApproved((a) => ({ ...a, [c.id]: e.target.checked }))} />
                          approve
                        </label>
                      )}
                      {prop.status === "applied" && (
                        <Badge tone={c.approved ? "good" : ""}>{c.approved ? "applied" : "not applied"}</Badge>
                      )}
                    </div>
                    {c.rationale && <div className="small muted" style={{ margin: "4px 0 8px" }}>{c.rationale}</div>}
                    <DiffView before={c.before} after={c.after} refs={refsMap} />
                  </div>
                ))}
              </div>

              {prop.status === "proposed" && (
                <div className="runbar" style={{ marginTop: 10 }}>
                  <button className="primary" onClick={() => void apply()}
                    disabled={!prop.integrity.ok || Object.values(approved).every((v) => !v)}>
                    Apply approved changes
                  </button>
                  <button className="pill" onClick={() => void reject()}>Reject all</button>
                  {!prop.integrity.ok && (
                    <span className="small" style={{ color: "var(--bad)" }}>
                      blocked: integrity violations must not be applied
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {paper.history.length > 0 && (
        <div className="card">
          <h3>Edit history</h3>
          <ul className="small">
            {paper.history.map((h) => (
              <li key={h.version}>v{h.version} → v{h.version + 1}: {h.reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
