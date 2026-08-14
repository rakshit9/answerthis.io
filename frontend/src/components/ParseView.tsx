import { useMemo, useState } from "react";
import type { Paper } from "../types";
import { Badge, ConfBar, ResolutionBadge } from "./bits";

export function ParseView({ paper, onResolve, resolving }: {
  paper: Paper; onResolve: () => void; resolving: boolean;
}) {
  const rep = paper.parse_report;
  const [filter, setFilter] = useState<"all" | "unparsed" | "unresolved">("all");

  const refs = useMemo(() => {
    if (filter === "unparsed") return paper.references.filter((r) => r.parse_confidence < 0.5);
    if (filter === "unresolved")
      return paper.references.filter((r) => !["resolved", "not_attempted"].includes(r.resolution.status));
    return paper.references;
  }, [paper, filter]);

  const nResolved = paper.references.filter((r) => r.resolution.status === "resolved").length;
  const nAttempted = paper.references.filter((r) => r.resolution.status !== "not_attempted").length;

  return (
    <div>
      <div className="stat-row">
        <div className="stat"><div className="n">{rep.n_pages}</div><div className="l">pages</div></div>
        <div className="stat"><div className="n">{paper.sections.filter((s) => s.kind === "body").length}</div><div className="l">body sections</div></div>
        <div className="stat good"><div className="n">{rep.n_references_parsed}</div><div className="l">references parsed</div></div>
        <div className={`stat ${rep.n_references_unparsed ? "warn" : ""}`}>
          <div className="n">{rep.n_references_unparsed}</div><div className="l">unparsed (kept, surfaced)</div>
        </div>
        <div className="stat"><div className="n">{rep.n_intext_citations}</div><div className="l">in-text citation groups</div></div>
        <div className={`stat ${rep.n_intext_unmatched ? "warn" : ""}`}>
          <div className="n">{rep.n_intext_unmatched}</div><div className="l">unlinked markers</div>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <h3>Detected structure</h3>
          <div className="small muted" style={{ marginBottom: 8 }}>
            In-text style: <Badge tone="accent">{rep.intext_style}</Badge>
            confidence {rep.intext_style_confidence}
            {paper.csl_style_detected
              ? <> → CSL style <Badge tone="accent">{paper.csl_style}</Badge> (auto-detected; change in Export)</>
              : <> → CSL style <Badge>{paper.csl_style}</Badge> (pick one in Export)</>}
          </div>
          <ul className="outline">
            {paper.sections.map((s) => (
              <li key={s.id} style={{ marginLeft: (s.level - 1) * 16 }}>
                {s.title || "(untitled)"}
                <span className="kind">{s.kind}{s.content ? ` · ${s.content.length} chars` : ""}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h3>How this PDF was parsed</h3>
          <div className="stage-log">
            {rep.stages.map((s, i) => <div key={i}>{s}</div>)}
            {rep.warnings.map((w, i) => (
              <div key={`w${i}`} className="warning-line" title={w.detail ?? ""}>
                ⚠ [{w.stage}] {w.message}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>References ({paper.references.length})</h3>
          <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
            <option value="all">all</option>
            <option value="unparsed">unparsed only</option>
            <option value="unresolved">resolution problems</option>
          </select>
          <span className="small muted">
            {nAttempted ? `${nResolved}/${nAttempted} resolved to external records` : "not yet resolved"}
          </span>
          <button className="pill" style={{ marginLeft: "auto", cursor: "pointer" }}
            onClick={onResolve} disabled={resolving}>
            {resolving ? <><span className="spin" />resolving…</> : "Resolve against OpenAlex / S2"}
          </button>
        </div>
        <table className="ref-table">
          <thead>
            <tr><th>#</th><th>parsed fields</th><th>conf</th><th>resolution</th></tr>
          </thead>
          <tbody>
            {refs.map((r) => (
              <tr key={r.id} className={r.parse_confidence < 0.5 ? "unparsed" : ""}>
                <td className="mono">{r.label ?? r.id.replace("ref_", "")}</td>
                <td>
                  {r.parse_confidence >= 0.5 ? (
                    <>
                      <strong>{r.parsed.title ?? "(no title)"}</strong>
                      <div className="small muted">
                        {r.parsed.authors.slice(0, 4).join("; ")}
                        {r.parsed.authors.length > 4 ? " …" : ""}
                        {r.parsed.year ? ` · ${r.parsed.year}` : ""}
                        {r.parsed.container ? ` · ${r.parsed.container}` : ""}
                        {r.parsed.doi ? ` · doi:${r.parsed.doi}` : ""}
                        {r.parsed.arxiv_id ? ` · arXiv:${r.parsed.arxiv_id}` : ""}
                      </div>
                      {r.added_by === "agent" && (
                        <div className="small" style={{ color: "var(--accent)" }}>
                          added by agent — {r.added_reason}
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <Badge tone="warn">could not parse</Badge>
                      <span className="small muted">{r.parse_issues.join("; ")}</span>
                      <div className="raw-text">{r.raw_text}</div>
                    </>
                  )}
                </td>
                <td><ConfBar v={r.parse_confidence} /></td>
                <td>
                  <ResolutionBadge r={r} />
                  {r.resolution.match_score != null && r.resolution.status === "resolved" &&
                    <span className="small muted"> {Math.round(r.resolution.match_score * 100)}%</span>}
                  {r.resolution.error && (
                    <div className="small" style={{ color: "var(--warn)" }}>{r.resolution.error}</div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
