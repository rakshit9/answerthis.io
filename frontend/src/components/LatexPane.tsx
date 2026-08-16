import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Paper } from "../types";

/** Live view of the paper rebuilt as LaTeX from the canonical model.
 *  Refetches whenever the paper version or CSL style changes, so an applied
 *  edit is immediately visible as regenerated LaTeX. */

type TexLine = { text: string; kind: "section" | "cmd" | "comment" | "bibitem" | "plain"; anchor?: string };

const SECTION_RE = /^\\(?:sub)*section\*?\{(.+?)\}/;
const CMD_RE = /^\\(documentclass|usepackage|title|author|date|maketitle|begin|end|bibliographystyle|setlength|newcommand)/;

function classify(tex: string): { lines: TexLine[]; outline: { label: string; anchor: string }[] } {
  const lines: TexLine[] = [];
  const outline: { label: string; anchor: string }[] = [];
  tex.split("\n").forEach((text, i) => {
    const sec = SECTION_RE.exec(text);
    if (sec) {
      const anchor = `tex-l${i}`;
      outline.push({ label: sec[1], anchor });
      lines.push({ text, kind: "section", anchor });
    } else if (text.trimStart().startsWith("%")) {
      lines.push({ text, kind: "comment" });
    } else if (text.startsWith("\\bibitem")) {
      const anchor = outline.some((o) => o.label === "References") ? undefined : `tex-l${i}`;
      if (anchor) outline.push({ label: "References", anchor });
      lines.push({ text, kind: "bibitem", anchor });
    } else if (CMD_RE.test(text)) {
      lines.push({ text, kind: "cmd" });
    } else {
      lines.push({ text, kind: "plain" });
    }
  });
  return { lines, outline };
}

/** Split a plain line so \citep{...}/\citet{...}/\cite{...} render as chips. */
function withCites(text: string, key: number) {
  const parts: React.ReactNode[] = [];
  const re = /\\cite[pt]?\{[^}]*\}/g;
  let last = 0; let m: RegExpExecArray | null; let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(<span key={`${key}-${k++}`} className="tx-cite">{m[0]}</span>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function LatexPane({ paper }: { paper: Paper }) {
  const [tex, setTex] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRebuilding(true); setError(null);
    api.exportTex(paper.id)
      .then(setTex)
      .catch((e) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setRebuilding(false));
  }, [paper.id, paper.version, paper.csl_style]);

  const parsed = useMemo(() => (tex ? classify(tex) : null), [tex]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!parsed) return <div className="muted" style={{ padding: 24 }}><span className="spin" /> Rebuilding LaTeX from the canonical model…</div>;

  return (
    <div className="texpane">
      <nav className="tex-outline">
        <div className="tex-outline-head">Structure</div>
        {parsed.outline.map((o) => (
          <button key={o.anchor} onClick={() =>
            document.getElementById(o.anchor)?.scrollIntoView({ behavior: "smooth", block: "start" })}>
            {o.label}
          </button>
        ))}
      </nav>
      <div className="tex-view">
        <div className="tex-caption">
          {rebuilding
            ? <><span className="spin" /> rebuilding…</>
            : <>main.tex · regenerated from the canonical model · v{paper.version} · {paper.csl_style}</>}
        </div>
        <pre>
          {parsed.lines.map((l, i) => (
            <div key={i} id={l.anchor} className={`tx-${l.kind}`}>
              {l.kind === "plain" || l.kind === "bibitem" ? withCites(l.text, i) : l.text}
              {"\n"}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
