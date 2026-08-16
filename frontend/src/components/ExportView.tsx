import { useEffect, useState } from "react";
import { api } from "../api";
import type { Paper, RenderedDoc, StyleInfo, StyleSample } from "../types";
import { Icon } from "./icons";

const FILES: [string, string][] = [
  ["main.tex", "sections + \\cite; bibliography in the selected style"],
  ["references.bib", "CSL-JSON → BibTeX (style-independent data)"],
  ["paper.md", "Markdown, labels formatted in the selected style"],
  ["paper.json", "canonical model"],
  ["PROVENANCE.md", "citation origins"],
];

export function ExportView({ paper, onStyleChange }: {
  paper: Paper; onStyleChange: () => void;
}) {
  const [styles, setStyles] = useState<StyleInfo[]>([]);
  const [samples, setSamples] = useState<Record<string, StyleSample>>({});
  const [view, setView] = useState<"paper" | "latex">("paper");
  const [doc, setDoc] = useState<RenderedDoc | null>(null);
  const [tex, setTex] = useState<string | null>(null);
  const [restyling, setRestyling] = useState(false);
  const [compare, setCompare] = useState(false);

  useEffect(() => { api.styles().then(setStyles).catch(() => {}); }, []);

  // Samples are rendered from this paper's own references, so they only move
  // when the document does.
  useEffect(() => {
    api.styleSamples(paper.id).then(setSamples).catch(() => setSamples({}));
  }, [paper.id, paper.version]);

  useEffect(() => { setDoc(null); setTex(null); }, [paper.id]);

  // Live preview follows version + style. The style is sent explicitly rather
  // than left to the stored default, so what is on screen is always the style
  // shown in the picker — including the moment right after a switch.
  useEffect(() => {
    let dead = false;
    setRestyling(true);
    Promise.all([
      api.rendered(paper.id, paper.csl_style),
      api.exportTex(paper.id, paper.csl_style),
    ]).then(([d, t]) => {
      if (dead) return;
      setDoc(d); setTex(t);
    }).catch(() => {}).finally(() => { if (!dead) setRestyling(false); });
    return () => { dead = true; };
  }, [paper.id, paper.version, paper.csl_style]);

  const changeStyle = async (style: string) => {
    setRestyling(true);
    await api.setStyle(paper.id, style);
    onStyleChange();
  };

  const active = styles.find((s) => s.id === paper.csl_style);
  const sample = samples[paper.csl_style];

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
            {restyling && (doc || tex)
              ? <><span className="spin" /> restyling in {active?.title ?? paper.csl_style}…</>
              : view === "paper"
                ? doc ? <>exactly what ships · {doc.style}</> : "rendering…"
                : "regenerated live"}
          </span>
        </div>
        <div className={`preview-body ${view === "latex" ? "dark" : ""} ${restyling ? "restyling" : ""}`}>
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
            <div className="style-field-note small muted">
              {restyling
                ? <><span className="spin" /> re-rendering the paper and main.tex…</>
                : <>the preview, <code>main.tex</code>, <code>paper.md</code> and the zip all follow this</>}
            </div>
            {paper.csl_style_detected && (
              <div style={{ marginTop: 6 }}>
                <span className="pill ok"><Icon.check size={13} /> auto-detected</span>
              </div>
            )}
          </div>
          <a className="dl" href={api.exportZipUrl(paper.id, paper.csl_style)} download>
            <button className="primary"><Icon.download size={15} /> Download zip</button>
          </a>
        </div>

        {/* what the selected style actually does to this paper */}
        <div className="card style-card">
          <h3><Icon.doc /> What this style changes</h3>
          {!active ? (
            <div className="small muted">Loading style details…</div>
          ) : (
            <>
              <div className="style-head">
                <span className="badge">{active.family ?? "citation style"}</span>
                <span className="small muted">{active.title}</span>
              </div>

              {sample?.parenthetical && (
                <dl className="style-samples">
                  <div>
                    <dt>In text</dt>
                    <dd>{sample.parenthetical}</dd>
                  </div>
                  {sample.group && (
                    <div>
                      <dt>Two works</dt>
                      <dd>{sample.group}</dd>
                    </div>
                  )}
                  {sample.narrative && (
                    <div>
                      <dt>Narrative</dt>
                      <dd><span className="muted">Author name</span> {sample.narrative}</dd>
                    </div>
                  )}
                  {sample.bibliography?.[0] && (
                    <div>
                      <dt>Reference</dt>
                      <dd className="wrap">{sample.bibliography[0]}</dd>
                    </div>
                  )}
                </dl>
              )}
              {sample?.parenthetical && (
                <p className="small muted style-sample-note">
                  Rendered from your own first cited reference.
                </p>
              )}

              <ul className="style-changes">
                {active.in_text && <li><b>In-text form</b> — {active.in_text}</li>}
                {active.bibliography && <li><b>Reference list</b> — {active.bibliography}</li>}
                {(active.changes ?? []).map((c) => <li key={c}>{c}</li>)}
              </ul>

              <button className="ghost style-compare-toggle" onClick={() => setCompare((v) => !v)}>
                {compare ? "Hide comparison" : "Compare all styles"}
              </button>
              {compare && (
                <ul className="style-compare">
                  {styles.map((s) => (
                    <li key={s.id} className={s.id === paper.csl_style ? "on" : ""}>
                      <button onClick={() => void changeStyle(s.id)} disabled={s.id === paper.csl_style}>
                        <span className="sc-name">{s.title}</span>
                        <span className="sc-sample">
                          {samples[s.id]?.parenthetical ?? (s.family ?? "")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
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
