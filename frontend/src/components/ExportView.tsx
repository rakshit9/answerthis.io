import { useEffect, useState } from "react";
import { api } from "../api";
import type { Paper, RenderedDoc, StyleInfo } from "../types";
import { Icon } from "./icons";

const FILES: [string, string][] = [
  ["main.tex", "natbib + citeproc"],
  ["references.bib", "CSL-JSON → BibTeX"],
  ["paper.md", "Markdown"],
  ["paper.json", "canonical model"],
  ["PROVENANCE.md", "citation origins"],
];

export function ExportView({ paper, onStyleChange }: {
  paper: Paper; onStyleChange: () => void;
}) {
  const [styles, setStyles] = useState<StyleInfo[]>([]);
  const [view, setView] = useState<"paper" | "latex">("paper");
  const [doc, setDoc] = useState<RenderedDoc | null>(null);
  const [tex, setTex] = useState<string | null>(null);

  useEffect(() => { api.styles().then(setStyles).catch(() => {}); }, []);

  // live preview follows version + style
  useEffect(() => {
    setDoc(null); setTex(null);
    api.rendered(paper.id).then(setDoc).catch(() => {});
    api.exportTex(paper.id).then(setTex).catch(() => {});
  }, [paper.id, paper.version, paper.csl_style]);

  const changeStyle = async (style: string) => {
    await api.setStyle(paper.id, style);
    onStyleChange();
  };

  return (
    <div className="export-split">
      {/* ------------------------------------------------ live preview -- */}
      <div className="export-preview">
        <div className="paper-pane-head">
          <div className="seg">
            <button className={view === "paper" ? "on" : ""} onClick={() => setView("paper")}>Paper</button>
            <button className={view === "latex" ? "on" : ""} onClick={() => setView("latex")}>main.tex</button>
          </div>
          <span className="small muted">
            {view === "paper"
              ? doc ? <>exactly what ships · {doc.style}</> : "rendering…"
              : "regenerated live"}
          </span>
        </div>
        <div className={`preview-body ${view === "latex" ? "dark" : ""}`}>
          {view === "paper" ? (
            !doc ? (
              <div className="muted" style={{ padding: 24 }}><span className="spin" /> Rendering with citeproc…</div>
            ) : (
              <article className="sheet reader">
                <h1 style={{ fontSize: 23, marginTop: 0 }}>{paper.meta.title}</h1>
                {paper.meta.authors.length > 0 && (
                  <div className="muted">{paper.meta.authors.join(", ")}</div>
                )}
                {doc.sections.map((s) => (
                  <section key={s.id}>
                    {s.kind === "abstract"
                      ? <h2>Abstract</h2>
                      : (s.level === 1 ? <h2>{s.title}</h2> : <h3>{s.title}</h3>)}
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
              </article>
            )
          ) : (
            !tex ? (
              <div className="muted" style={{ padding: 24, color: "#8b95a7" }}>
                <span className="spin" /> Rendering main.tex…
              </div>
            ) : (
              <pre style={{
                margin: 0, padding: "14px 18px 60px", fontFamily: "var(--mono)",
                fontSize: 12, lineHeight: 1.7, color: "#c9d1d9",
                whiteSpace: "pre-wrap", wordBreak: "break-word",
              }}>{tex}</pre>
            )
          )}
        </div>
      </div>

      {/* ------------------------------------------------ export options -- */}
      <aside className="export-side">
        <div className="card">
          <h3><Icon.download /> Export</h3>
          <div className="field">
            <label>Citation style</label>
            <select value={paper.csl_style} onChange={(e) => void changeStyle(e.target.value)}>
              {styles.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
            {paper.csl_style_detected && (
              <div style={{ marginTop: 6 }}>
                <span className="pill ok"><Icon.check size={13} /> auto-detected</span>
              </div>
            )}
          </div>
          <a className="dl" href={api.exportZipUrl(paper.id)} download>
            <button className="primary"><Icon.download size={15} /> Download zip</button>
          </a>
        </div>
        <div className="card">
          <h3><Icon.doc /> Contents</h3>
          <ul className="export-list">
            {FILES.map(([f, why]) => (
              <li key={f}><code>{f}</code> — {why}</li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
