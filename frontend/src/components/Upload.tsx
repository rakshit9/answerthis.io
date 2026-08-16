import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { DropIllustration, Icon } from "./icons";

const STEPS: [string, () => JSX.Element][] = [
  ["Parse", Icon.pages],
  ["Review", Icon.search],
  ["Edit", Icon.pencil],
  ["Export", Icon.download],
];

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
    <div className="fade-up">
      <div className="upload-hero">
        <h1>Improve your paper<br />before you submit.</h1>
        <p className="sub">Peer review grounded in real citations.</p>

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
            <>
              <DropIllustration active />
              <div className="big"><span className="spin" /> Parsing…</div>
            </>
          ) : (
            <>
              <DropIllustration active={drag} />
              <div className="big">Drop a paper PDF</div>
              <div className="hint">arXiv works best</div>
              <button onClick={() => fileRef.current?.click()}>
                <Icon.upload /> Choose PDF
              </button>
              <input ref={fileRef} type="file" accept="application/pdf" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void doUpload(f); }} />
            </>
          )}
        </div>

        {error && <div className="error-banner" style={{ marginTop: 14 }}>
          <Icon.alert /> {error}
        </div>}

        <div className="steps-note">
          {STEPS.map(([label, Ico], i) => (
            <span key={label} className="step">
              <span className="step-ico"><Ico /></span>{label}
              {i < STEPS.length - 1 && <i className="step-arrow"><Icon.arrow size={13} /></i>}
            </span>
          ))}
        </div>
      </div>

      {recent.length > 0 && (
        <div className="recent">
          <h3>Recent</h3>
          {recent.map((p) => (
            <div className="card row-card" key={p.id} onClick={() => onOpen(p.id)}>
              <span className="row-ico"><Icon.doc /></span>
              <span className="row-main">
                <strong>{p.title || p.filename}</strong>
                <span className="small muted">{p.n_references} refs · v{p.version}</span>
              </span>
              <span className="row-go"><Icon.arrow size={15} /></span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
