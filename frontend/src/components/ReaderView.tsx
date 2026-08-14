import { useEffect, useState } from "react";
import { api } from "../api";
import type { Paper, RenderedDoc } from "../types";

export function ReaderView({ paper }: { paper: Paper }) {
  const [doc, setDoc] = useState<RenderedDoc | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDoc(null);
    api.rendered(paper.id).then(setDoc).catch((e) => setError(String(e.message ?? e)));
  }, [paper.id, paper.version, paper.csl_style]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!doc) return <div className="muted"><span className="spin" /> Rendering with citeproc…</div>;

  return (
    <div className="reader">
      <div className="small muted" style={{ fontFamily: "var(--sans)" }}>
        Citations rendered in CSL style <strong>{doc.style}</strong> · document v{paper.version}
      </div>
      <h1 style={{ fontSize: 26 }}>{paper.meta.title}</h1>
      {paper.meta.authors.length > 0 && (
        <div className="muted">{paper.meta.authors.join(", ")}</div>
      )}
      {doc.sections.map((s) => (
        <section key={s.id}>
          {s.kind !== "abstract" && (s.level === 1
            ? <h2>{s.title}</h2> : <h3>{s.title}</h3>)}
          {s.kind === "abstract" && <h2>Abstract</h2>}
          {s.html.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}
        </section>
      ))}
      <h2>References</h2>
      {doc.bibliography.map((b) => (
        <div key={b.ref_id} className={`bib-entry ${b.raw_fallback ? "raw" : ""}`}>
          <span className="bib-id">{b.ref_id}</span>
          {b.formatted}
          {b.raw_fallback && <span className="small"> — unparsed, raw text shown</span>}
        </div>
      ))}
    </div>
  );
}
