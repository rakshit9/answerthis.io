import { useMemo, useState } from "react";
import type { Paper } from "../types";
import { Badge, ConfBar, ResolutionBadge } from "./bits";
import { Icon } from "./icons";

function Stat({ n, label, tone, ico: Ico }: {
  n: number; label: string; tone?: string; ico: () => JSX.Element;
}) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <span className="stat-ico"><Ico /></span>
      <div className="n">{n}</div>
      <div className="l">{label}</div>
    </div>
  );
}

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
    <div className="fade-up">
      <div className="stat-row">
        <Stat n={rep.n_pages} label="pages" ico={Icon.pages} />
        <Stat n={paper.sections.filter((s) => s.kind === "body").length} label="sections" ico={Icon.sections} />
        <Stat n={rep.n_references_parsed} label="references" tone="good" ico={Icon.quote} />
        <Stat n={rep.n_references_unparsed} label="unparsed" ico={Icon.alert}
          tone={rep.n_references_unparsed ? "warn" : ""} />
        <Stat n={rep.n_intext_citations} label="citations" ico={Icon.link} />
        <Stat n={rep.n_intext_unmatched} label="unlinked" ico={Icon.unlink}
          tone={rep.n_intext_unmatched ? "warn" : ""} />
        <Stat n={rep.n_floats ?? 0} label="floats" ico={Icon.image} />
      </div>

      <div className="grid2">
        <div className="card">
          <h3><Icon.sections /> Structure</h3>
          <div className="small muted" style={{ marginBottom: 10 }}>
            <Badge tone="accent">{rep.intext_style}</Badge>
            <Badge tone={paper.csl_style_detected ? "accent" : undefined}>{paper.csl_style}</Badge>
            {paper.csl_style_detected ? "auto-detected" : "set in Export"}
          </div>
          <ul className="outline">
            {paper.sections.map((s) => (
              <li key={s.id} style={{ marginLeft: (s.level - 1) * 14 }}>
                <span className="outline-title">{s.title || "(untitled)"}</span>
                <span className="kind">
                  {s.kind !== "body" ? s.kind : s.content.length > 950
                    ? `${(s.content.length / 1000).toFixed(1)}k` : `${s.content.length}`}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h3><Icon.spark /> Parse trace</h3>
          <ol className="stage-steps">
            {rep.stages.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          {rep.warnings.length > 0 && (
            <div className="warn-groups">
              {Object.entries(
                rep.warnings.reduce<Record<string, typeof rep.warnings>>((acc, w) => {
                  (acc[w.stage] ??= []).push(w);
                  return acc;
                }, {})
              ).map(([stage, ws]) => (
                <details key={stage}>
                  <summary>
                    <Badge tone="warn">{ws.length}</Badge> {stage} warning{ws.length === 1 ? "" : "s"}
                  </summary>
                  <div className="warn-list">
                    {ws.map((w, i) => (
                      <div key={i} className="warning-line" title={w.detail ?? ""}>{w.message}</div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}
          {(paper.floats?.length ?? 0) > 0 && (
            <div style={{ marginTop: 18 }}>
              <h3 style={{ marginBottom: 4 }}><Icon.image /> Floats</h3>
              <div className="small muted" style={{ marginBottom: 8 }}>
                Text preserved · layout not reconstructed
              </div>
              {paper.floats.map((f) => (
                <details key={f.id} className="float-item">
                  <summary>
                    <Badge tone="accent">{f.kind}</Badge>
                    <span className="float-cap">{f.caption || <em className="muted">no caption</em>}</span>
                    <span className="small muted">p{f.page + 1}</span>
                  </summary>
                  <pre className="float-body">{f.text || "(no extractable text — likely a vector drawing)"}</pre>
                </details>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}><Icon.quote /> References ({paper.references.length})</h3>
          <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
            <option value="all">all</option>
            <option value="unparsed">unparsed only</option>
            <option value="unresolved">problems</option>
          </select>
          <span className="small muted">
            {nAttempted ? `${nResolved}/${nAttempted} resolved` : "not resolved"}
          </span>
          <button className="primary" style={{ marginLeft: "auto" }}
            onClick={onResolve} disabled={resolving}>
            {resolving ? <><span className="spin" />Resolving…</> : <><Icon.search size={15} /> Resolve</>}
          </button>
        </div>
        <div className="ref-table-wrap">
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
    </div>
  );
}
