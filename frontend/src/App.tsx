import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Health, Paper } from "./types";
import { Upload } from "./components/Upload";
import { ParseView } from "./components/ParseView";
import { ReaderView } from "./components/ReaderView";
import { ReviewView } from "./components/ReviewView";
import { EditView } from "./components/EditView";
import { ExportView } from "./components/ExportView";

type Tab = "parse" | "reader" | "review" | "edit" | "export";

export default function App() {
  const [paperId, setPaperId] = useState<string | null>(null);
  const [paper, setPaper] = useState<Paper | null>(null);
  const [tab, setTab] = useState<Tab>("parse");
  const [health, setHealth] = useState<Health | null>(null);
  const [resolving, setResolving] = useState(false);
  const resolveTimer = useRef<number | null>(null);

  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);

  const refresh = useCallback(() => {
    if (paperId) api.paper(paperId).then(setPaper).catch(() => {});
  }, [paperId]);

  useEffect(() => { refresh(); }, [refresh]);

  const openPaper = (id: string) => { setPaperId(id); setTab("parse"); };

  const startResolve = async () => {
    if (!paperId) return;
    setResolving(true);
    await api.startResolve(paperId);
    const tick = () => {
      api.resolveStatus(paperId).then((s) => {
        refresh();
        if (!s.done) resolveTimer.current = window.setTimeout(tick, 2000);
        else setResolving(false);
      }).catch(() => setResolving(false));
    };
    tick();
  };

  useEffect(() => () => {
    if (resolveTimer.current) window.clearTimeout(resolveTimer.current);
  }, []);

  return (
    <div>
      <div className="topbar">
        <div className="logo" style={{ cursor: "pointer" }}
          onClick={() => { setPaperId(null); setPaper(null); }}>
          Paper<span>Improvement</span>Agent
        </div>
        {paper && <div className="paper-title">{paper.meta.title || paper.filename} · v{paper.version}</div>}
        <div className="spacer" />
        {health && (
          <span className={`pill ${health.llm ? "ok" : "warn"}`}
            title={health.llm_hint ?? undefined}>
            {health.llm ? `LLM: ${health.llm}` : "no LLM configured"}
          </span>
        )}
        {health && (
          <span className="pill" title="Semantic Scholar API key raises rate limits (optional)">
            S2 key: {health.semantic_scholar_key ? "yes" : "no"}
          </span>
        )}
      </div>

      {!paperId && <Upload onOpen={openPaper} />}

      {paperId && paper && (
        <div className="workspace">
          <nav className="sidebar">
            {([
              ["parse", "1 · Parse", null],
              ["reader", "2 · Read", null],
              ["review", "3 · Peer review", null],
              ["edit", "4 · Edit", null],
              ["export", "5 · Export", null],
            ] as [Tab, string, null][]).map(([t, label]) => (
              <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                {label}
              </button>
            ))}
          </nav>
          <main className="main">
            {tab === "parse" && <ParseView paper={paper} onResolve={() => void startResolve()} resolving={resolving} />}
            {tab === "reader" && <ReaderView paper={paper} />}
            {tab === "review" && <ReviewView paper={paper} llm={health?.llm ?? null} />}
            {tab === "edit" && <EditView paper={paper} llm={health?.llm ?? null} onApplied={refresh} />}
            {tab === "export" && <ExportView paper={paper} onStyleChange={refresh} />}
          </main>
        </div>
      )}

      {paperId && !paper && (
        <div style={{ padding: 40 }} className="muted"><span className="spin" /> Loading paper…</div>
      )}
    </div>
  );
}
