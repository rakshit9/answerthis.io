import type { ExternalSource, Reference } from "../types";

export function Badge({ tone, children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`badge ${tone ?? ""}`}>{children}</span>;
}

export function ConfBar({ v }: { v: number }) {
  const color = v >= 0.8 ? "var(--good)" : v >= 0.5 ? "var(--warn)" : "var(--bad)";
  return (
    <span title={`parse confidence ${v}`}>
      <span className="conf-bar"><i style={{ width: `${v * 100}%`, background: color }} /></span>
      <span className="small muted">{v.toFixed(1)}</span>
    </span>
  );
}

export function ResolutionBadge({ r }: { r: Reference }) {
  const s = r.resolution.status;
  if (s === "resolved")
    return (
      <a href={r.resolution.source_url ?? undefined} target="_blank" rel="noreferrer">
        <Badge tone="good">{r.resolution.source === "openalex" ? "OpenAlex" : "S2"} ↗</Badge>
      </a>
    );
  if (s === "ambiguous") return <Badge tone="warn" >ambiguous</Badge>;
  if (s === "unresolved") return <Badge tone="warn">not found</Badge>;
  if (s === "failed") return <Badge tone="bad" >lookup failed</Badge>;
  return <Badge>unresolved</Badge>;
}

export function SourceLine({ s }: { s: ExternalSource }) {
  return (
    <div className="source-line">
      <a href={s.url} target="_blank" rel="noreferrer"><strong>{s.title}</strong></a>{" "}
      <span className="muted">
        {s.authors.slice(0, 3).join(", ")}{s.authors.length > 3 ? " et al." : ""}
        {s.year ? ` · ${s.year}` : ""}{s.venue ? ` · ${s.venue}` : ""}
        {typeof s.cited_by_count === "number" ? ` · ${s.cited_by_count} citations` : ""}
        {" · via "}{s.api === "openalex" ? "OpenAlex" : "Semantic Scholar"}
        {s.doi ? <> · <a href={`https://doi.org/${s.doi}`} target="_blank" rel="noreferrer">doi</a></> : null}
      </span>
    </div>
  );
}

/** Render text that may contain [[citep:...]] tokens as chips. */
export function TokenText({ text, refs }: { text: string; refs: Map<string, Reference> }) {
  const parts: React.ReactNode[] = [];
  const re = /\[\[cite([pt]):([A-Za-z0-9_,\- ]+?)\]\]/g;
  let last = 0; let m: RegExpExecArray | null; let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const ids = m[2].split(",").map((s) => s.trim()).filter(Boolean);
    const title = ids.map((id) => {
      const r = refs.get(id);
      const a = r?.parsed.authors[0]?.split(",")[0] ?? id;
      return r?.parsed.year ? `${a} ${r.parsed.year}` : a;
    }).join("; ");
    parts.push(<span key={k++} className="chip" title={title}>
      {ids.map((id) => refs.get(id)?.label ?? id.replace("ref_", "r")).join(",")}
    </span>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}
