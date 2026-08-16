import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Paper } from "../types";
import { Loading } from "./Loading";
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
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const dirty = editing !== null && draft !== original;

  // Grow the textarea to its content: an editor with its own inner scrollbar
  // inside an already-scrolling file reads as a text box bolted onto the
  // page, not as the file itself being editable.
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight}px`;
  }, [draft, editing]);

  useEffect(() => {
    setRebuilding(true); setError(null);
    api.exportTex(paper.id)
      .then(setTex)
      .catch((e) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setRebuilding(false));
  }, [paper.id, paper.version, paper.csl_style]);

  const parsed = useMemo(() => (tex ? toBlocks(tex, paper) : null), [tex, paper]);

  const beginEdit = (sectionId: string) => {
    // Switching sections mid-edit would drop unsaved text, so ask first.
    if (dirty && editing !== sectionId &&
        !window.confirm("Discard unsaved changes to the section you're editing?")) return;
    const content = paper.sections.find((s) => s.id === sectionId)?.content ?? "";
    const body = toLatexBody(content);
    setEditing(sectionId);
    setDraft(body);
    setOriginal(body);
    setEditError(null);
  };

  const cancelEdit = () => {
    if (dirty && !window.confirm("Discard your changes to this section?")) return;
    setEditing(null);
    setEditError(null);
  };

  const saveEdit = async () => {
    if (!editing) return;
    const sectionId = editing;
    setSaving(true); setEditError(null);
    try {
      await api.editSection(paper.id, sectionId, fromLatexBody(draft), paper.version);
      setEditing(null);
      setJustSaved(sectionId);
      window.setTimeout(() => setJustSaved((s) => (s === sectionId ? null : s)), 2200);
      onChanged();                       // version bumps → tex refetches
    } catch (e) {
      setEditError(String(e instanceof Error ? e.message : e));
    } finally { setSaving(false); }
  };

  /** ⌘/Ctrl+Enter saves, Esc cancels — the shortcuts an editor implies. */
  const onEditorKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void saveEdit(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
  };

  const copyTex = () => {
    if (!tex) return;
    void navigator.clipboard.writeText(tex).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    });
  };

  if (error) return <div className="error-banner">{error}</div>;
  if (!parsed) return <Loading label="Rebuilding LaTeX from the canonical model…" />;

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
                    {!isEditing && justSaved !== b.sectionId && (
                      <button className="tx-edit-btn" title="Edit this section directly"
                        onClick={() => beginEdit(b.sectionId)}>
                        <Icon.pencil size={11} /> edit
                      </button>
                    )}
                    {justSaved === b.sectionId && (
                      <span className="tx-saved"><Icon.check size={11} /> saved</span>
                    )}
                    {"\n"}
                  </div>
                  {isEditing ? (
                    <div className="tex-sec-editor">
                      <textarea ref={taRef} value={draft} autoFocus spellCheck={false}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={onEditorKeyDown} />
                      {editError && <div className="error-banner">{editError}</div>}
                      <div className="tex-sec-bar">
                        <span className="hint">
                          \citep{"{…}"} commands are live citations — keep or delete, don't invent.
                          {dirty && <b className="tex-dirty"> unsaved</b>}
                        </span>
                        <span className="tex-keys">⌘⏎ save · esc cancel</span>
                        <button className="tex-tool" disabled={saving}
                          onClick={cancelEdit}>Cancel</button>
                        <button className="tex-tool save" disabled={saving || !dirty}
                          onClick={() => void saveEdit()}>
                          {saving ? "Saving…" : "Save"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    // The body itself is the edit affordance — click the text
                    // you want to change, the way you would in a real file.
                    <div className="tx-body" title="Click to edit this section"
                      onClick={() => beginEdit(b.sectionId)}>
                      {b.body.map((l, i) => (
                        <div key={i} className={`tx-${l.kind}`}>
                          {l.kind === "plain" ? withCites(l.text, bi * 1000 + i) : l.text}
                          {"\n"}
                        </div>
                      ))}
                    </div>
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
