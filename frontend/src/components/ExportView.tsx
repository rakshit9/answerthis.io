import { useEffect, useState } from "react";
import { api } from "../api";
import type { Paper, StyleInfo } from "../types";

export function ExportView({ paper, onStyleChange }: {
  paper: Paper; onStyleChange: () => void;
}) {
  const [styles, setStyles] = useState<StyleInfo[]>([]);
  const [tex, setTex] = useState<string | null>(null);
  const [loadingTex, setLoadingTex] = useState(false);

  useEffect(() => { api.styles().then(setStyles).catch(() => {}); }, []);
  useEffect(() => { setTex(null); }, [paper.version, paper.csl_style]);

  const changeStyle = async (style: string) => {
    await api.setStyle(paper.id, style);
    onStyleChange();
  };

  const preview = async () => {
    setLoadingTex(true);
    try { setTex(await api.exportTex(paper.id)); }
    finally { setLoadingTex(false); }
  };

  return (
    <div>
      <div className="card">
        <h3>Export the revised paper</h3>
        <p className="small muted">
          The zip rebuilds the paper as LaTeX: <code>main.tex</code> (citations as
          natbib/cite commands, bibliography text rendered by citeproc in the
          selected CSL style), <code>references.bib</code> (canonical CSL-JSON →
          BibTeX), <code>paper.md</code>, <code>paper.json</code> (full canonical
          model), and <code>PROVENANCE.md</code> (where every agent-added citation
          came from, plus edit history).
        </p>
        <div className="runbar">
          <label className="checklabel">
            Citation style (CSL):&nbsp;
            <select value={paper.csl_style} onChange={(e) => void changeStyle(e.target.value)}>
              {styles.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
          </label>
          {paper.csl_style_detected && <span className="pill ok">auto-detected from the PDF</span>}
          <a href={api.exportZipUrl(paper.id)} download>
            <button className="primary">Download LaTeX zip</button>
          </a>
          <button className="pill" onClick={() => void preview()} disabled={loadingTex}>
            {loadingTex ? "rendering…" : "Preview main.tex"}
          </button>
        </div>
      </div>
      {tex && (
        <div className="card">
          <h3>main.tex</h3>
          <div className="tex-preview">{tex}</div>
        </div>
      )}
    </div>
  );
}
