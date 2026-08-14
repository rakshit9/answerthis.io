import { useEffect, useRef, useState } from "react";
import { api } from "../api";

export function Upload({ onOpen }: { onOpen: (id: string) => void }) {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<{ id: string; title: string; filename: string; n_references: number; version: number }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.papers().then(setRecent).catch(() => {}); }, []);

  const doUpload = async (file: File) => {
    setBusy(true); setError(null);
    try {
      const res = await api.upload(file);
      onOpen(res.id);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="upload-hero">
        <h1>Improve your paper before you submit it.</h1>
        <p className="sub">
          Upload a research paper PDF. Get a peer review grounded in real academic
          search (Semantic Scholar &amp; OpenAlex), then edit by instruction —
          with your citations kept intact.
        </p>
        <div
          className={`dropzone ${drag ? "drag" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault(); setDrag(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void doUpload(f);
          }}
        >
          {busy ? (
            <div className="big"><span className="spin" /> Parsing your PDF…</div>
          ) : (
            <>
              <div className="big">Drop your paper PDF here</div>
              <div className="hint">arXiv papers work well — their citations resolve on both search APIs</div>
              <button onClick={() => fileRef.current?.click()}>Choose PDF</button>
              <input ref={fileRef} type="file" accept="application/pdf" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void doUpload(f); }} />
            </>
          )}
        </div>
        {error && <div className="error-banner" style={{ marginTop: 14 }}>{error}</div>}
        <div className="steps-note">
          1 · Upload &amp; see the parse&nbsp;&nbsp;→&nbsp;&nbsp;2 · Request a peer
          review&nbsp;&nbsp;→&nbsp;&nbsp;3 · Edit by instruction&nbsp;&nbsp;→&nbsp;&nbsp;4 · Export LaTeX
        </div>
      </div>
      {recent.length > 0 && (
        <div className="recent">
          <h3>Recent papers</h3>
          {recent.map((p) => (
            <div className="card" key={p.id} onClick={() => onOpen(p.id)}>
              <strong>{p.title || p.filename}</strong>
              <div className="small muted">{p.n_references} references · v{p.version}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
