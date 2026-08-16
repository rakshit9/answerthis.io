import { useRef, useState } from "react";
import { api } from "../api";
import { DropIllustration, Icon } from "./icons";

const STEPS: [string, () => JSX.Element][] = [
  ["Parse", Icon.pages],
  ["Review", Icon.search],
  ["Edit", Icon.pencil],
  ["Export", Icon.download],
];

export function Upload({ onParsing }: {
  onParsing: (id: string, filename: string) => void;
}) {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const doUpload = async (file: File) => {
    setBusy(true); setError(null);
    try {
      const res = await api.upload(file);
      onParsing(res.id, file.name);        // parsing runs in the background
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
              <div className="big"><span className="spin" /> Uploading…</div>
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
    </div>
  );
}
