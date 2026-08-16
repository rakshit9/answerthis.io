import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Paper } from "../types";
import { Icon } from "./icons";

/** Live LaTeX view with direct editing.
 *
 *  The .tex file is generated output, so "editing the LaTeX" is made honest
 *  by a faithful round trip: a section's body is its canonical text with
 *  [[citep:…]] tokens rendered as \citep{…}. Edits convert back and save
 *  through the same section endpoint the reader uses — then the whole file
 *  regenerates, so what you see is always what exports. */

type TexLine = { text: string; kind: "section" | "cmd" | "comment" | "bibitem" | "plain"; anchor?: string };
type Block =
  | { kind: "raw"; lines: TexLine[] }
  | { kind: "section"; sectionId: string; head: TexLine; body: TexLine[] };

const SECTION_RE = /^\\(?:sub)*section\*?\{(.+?)\}/;
const CMD_RE = /^\\(documentclass|usepackage|title|author|date|maketitle|begin|end|bibliographystyle|setlength|newcommand)/;

/** LaTeX escapes the exporter applies to titles — undo them to match
 *  section titles back to their canonical Section records. */
const unescapeTex = (s: string) =>
  s.replace(/\\([&%$#_{}])/g, "$1").replace(/\\textasciitilde\{\}/g, "~");

const toLatexBody = (content: string) =>
  content.replace(/\[\[cite([pt]):([A-Za-z0-9_,\- ]+?)\]\]/g,
    (_m, k, ids) => `\\cite${k}{${String(ids).replace(/\s/g, "")}}`);
const fromLatexBody = (text: string) =>
  text.replace(/\\cite([pt])\{([^}]*)\}/g, (_m, k, ids) => `[[cite${k}:${ids}]]`);

function classifyLine(text: string): TexLine {
  if (SECTION_RE.test(text)) return { text, kind: "section" };
  if (text.trimStart().startsWith("%")) return { text, kind: "comment" };
  if (text.startsWith("\\bibitem")) return { text, kind: "bibitem" };
  if (CMD_RE.test(text)) return { text, kind: "cmd" };
  return { text, kind: "plain" };
}

function toBlocks(tex: string, paper: Paper): {
  blocks: Block[]; outline: { label: string; anchor: string }[];
} {
  const blocks: Block[] = [];
  const outline: { label: string; anchor: string }[] = [];
  let current: Block = { kind: "raw", lines: [] };
  const push = () => {
    if (current.kind === "raw" ? current.lines.length : true) blocks.push(current);
  };
  tex.split("\n").forEach((raw, i) => {
    const line = classifyLine(raw);
    const sec = line.kind === "section" ? SECTION_RE.exec(raw) : null;
    if (sec) {
      push();
      const anchor = `tex-l${i}`;
      line.anchor = anchor;
      outline.push({ label: sec[1], anchor });
      const canonical = paper.sections.find(
        (s) => s.title === unescapeTex(sec[1]) && s.content);
      current = canonical
        ? { kind: "section", sectionId: canonical.id, head: line, body: [] }
        : { kind: "raw", lines: [line] };
      return;
    }
    if (line.kind === "bibitem") {
      if (!outline.some((o) => o.label === "References")) {
        line.anchor = `tex-l${i}`;
        outline.push({ label: "References", anchor: line.anchor });
      }
      if (current.kind === "section") { push(); current = { kind: "raw", lines: [] }; }
      current.lines.push(line);
      return;
    }
    if (current.kind === "section") current.body.push(line);
    else current.lines.push(line);
  });
  push();
  return { blocks, outline };
}

/** Render \citep{...}/\citet{...} inside a line as chips. */
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

export function LatexPane({ paper, onChanged }: {
  paper: Paper; onChanged: () => void;
}) {
  const [tex, setTex] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // ---- direct editing of one section's body ----
  const [editing, setEditing] = useState<string | null>(null);   // sectionId
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    setRebuilding(true); setError(null);
    api.exportTex(paper.id)
      .then(setTex)
      .catch((e) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setRebuilding(false));
  }, [paper.id, paper.version, paper.csl_style]);

  const parsed = useMemo(() => (tex ? toBlocks(tex, paper) : null), [tex, paper]);

  const beginEdit = (sectionId: string) => {
    const content = paper.sections.find((s) => s.id === sectionId)?.content ?? "";
    setEditing(sectionId);
    setDraft(toLatexBody(content));
    setEditError(null);
  };

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true); setEditError(null);
    try {
      await api.editSection(paper.id, editing, fromLatexBody(draft), paper.version);
      setEditing(null);
      onChanged();                       // version bumps → tex refetches
    } catch (e) {
      setEditError(String(e instanceof Error ? e.message : e));
    } finally { setSaving(false); }
  };

  const copyTex = () => {
    if (!tex) return;
    void navigator.clipboard.writeText(tex).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    });
  };

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

      <div className="tex-editor">
        <div className="tex-head">
          <span className="tex-file"><Icon.doc size={13} /> main.tex</span>
          <span className="tex-meta">
            {rebuilding ? <><span className="spin" /> rebuilding…</>
              : <>v{paper.version} · {paper.csl_style} · regenerated live</>}
          </span>
          <span className="spacer" />
          <button className="tex-tool" onClick={copyTex}>
            {copied ? <><Icon.check size={13} /> Copied</> : "Copy"}
          </button>
        </div>

        <div className="tex-scroll">
          <pre className="tex-code">
            {parsed.blocks.map((b, bi) => {
              if (b.kind === "raw") {
                return b.lines.map((l, i) => (
                  <div key={`${bi}-${i}`} id={l.anchor} className={`tx-${l.kind}`}>
                    {l.kind === "plain" || l.kind === "bibitem" ? withCites(l.text, bi * 1000 + i) : l.text}
                    {"\n"}
                  </div>
                ));
              }
              const isEditing = editing === b.sectionId;
              return (
                <div key={bi} className={`tex-sec ${isEditing ? "editing" : ""}`}>
                  <div id={b.head.anchor} className="tx-section tx-editable">
                    {b.head.text}
                    {!isEditing && (
                      <button className="tx-edit-btn" title="Edit this section directly"
                        onClick={() => beginEdit(b.sectionId)}>
                        <Icon.pencil size={11} /> edit
                      </button>
                    )}
                    {"\n"}
                  </div>
                  {isEditing ? (
                    <div className="tex-sec-editor">
                      <textarea value={draft} autoFocus spellCheck={false}
                        onChange={(e) => setDraft(e.target.value)} />
                      {editError && <div className="error-banner">{editError}</div>}
                      <div className="tex-sec-bar">
                        <span className="hint">\citep{"{…}"} commands are live citations — keep or delete, don't invent.</span>
                        <button className="tex-tool" disabled={saving}
                          onClick={() => setEditing(null)}>Cancel</button>
                        <button className="tex-tool save" disabled={saving}
                          onClick={() => void saveEdit()}>
                          {saving ? "Saving…" : "Save"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    b.body.map((l, i) => (
                      <div key={i} className={`tx-${l.kind}`}>
                        {l.kind === "plain" ? withCites(l.text, bi * 1000 + i) : l.text}
                        {"\n"}
                      </div>
                    ))
                  )}
                </div>
              );
            })}
          </pre>
        </div>
      </div>
    </div>
  );
}
