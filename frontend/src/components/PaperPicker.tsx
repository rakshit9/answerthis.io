import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Icon } from "./icons";

type Row = {
  id: string; title: string; filename: string;
  n_references: number; version: number; uploaded_at?: number;
};

/** Papers are usually versions of the same manuscript, so titles repeat and
 *  the upload time is what actually tells two rows apart. */
function when(ts?: number): string {
  if (!ts) return "";
  const mins = Math.round((Date.now() - ts * 1000) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

/** Switch between parsed papers from the breadcrumb.
 *
 *  Every paper the backend has parsed is still there — it just had no route
 *  in the UI, so the only way to reach one was to upload it again, which
 *  reparses it and leaves a duplicate behind. The list is fetched when the
 *  menu opens rather than held in state, so it reflects papers parsed in
 *  another tab too. */
export function PaperPicker({ current, onPick, onUpload }: {
  current: { id: string; title: string; version: number };
  onPick: (id: string) => void;
  onUpload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [q, setQ] = useState("");
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) { setQ(""); return; }
    api.papers()
      .then((ps) => setRows([...ps].sort(
        (a: Row, b: Row) => (b.uploaded_at ?? 0) - (a.uploaded_at ?? 0))))
      .catch(() => setRows([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const needle = q.trim().toLowerCase();
  const others = (rows ?? [])
    .filter((r) => r.id !== current.id)
    .filter((r) => !needle
      || `${r.title} ${r.filename}`.toLowerCase().includes(needle));

  return (
    <div className="paper-picker" ref={box}>
      <button className="paper-title" onClick={() => setOpen((o) => !o)}
        title="Switch paper">
        {current.title}
        <Icon.chevron size={13} />
      </button>

      {open && (
        <div className="picker-menu">
          {rows === null && <div className="picker-empty"><span className="spin" /> loading…</div>}
          {rows !== null && (
            <>
              {/* Only worth a search box once the list stops fitting the eye. */}
              {(rows.length > 8) && (
                <input className="picker-search" autoFocus value={q}
                  placeholder="Filter by title or filename…"
                  onChange={(e) => setQ(e.target.value)} />
              )}
              <div className="picker-head">
                Parsed papers <span>{rows.length}</span>
              </div>
              {!needle && (
                <button className="picker-row on" onClick={() => setOpen(false)}>
                  <span className="picker-name">{current.title}</span>
                  <span className="picker-meta">v{current.version} · current</span>
                </button>
              )}
              {others.map((r) => (
                <button key={r.id} className="picker-row"
                  onClick={() => { setOpen(false); onPick(r.id); }}>
                  <span className="picker-name">{r.title || r.filename}</span>
                  <span className="picker-meta">
                    {when(r.uploaded_at)} · v{r.version} · {r.n_references} refs · {r.filename}
                  </span>
                </button>
              ))}
              {others.length === 0 && (
                <div className="picker-empty">
                  {needle ? `Nothing matches “${q}”.` : "No other papers parsed yet."}
                </div>
              )}
              <button className="picker-row upload"
                onClick={() => { setOpen(false); onUpload(); }}>
                <Icon.upload size={13} /> Upload a new paper
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
