import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Health, Paper } from "./types";
import { Upload } from "./components/Upload";
import { ParseView } from "./components/ParseView";
import { Workspace } from "./components/Workspace";
import { ExportView } from "./components/ExportView";

type Tab = "parse" | "paper" | "export";
type PaperListItem = { id: string; title: string; filename: string; n_references: number; version: number };

import { Icon } from "./components/icons";

export default function App() {
  const [paperId, setPaperId] = useState<string | null>(null);
  const [paper, setPaper] = useState<Paper | null>(null);
  const [tab, setTab] = useState<Tab>("parse");
  const [health, setHealth] = useState<Health | null>(null);
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [resolving, setResolving] = useState(false);
  const resolveTimer = useRef<number | null>(null);

  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);

  const refreshList = useCallback(() => {
    api.papers().then(setPapers).catch(() => {});
  }, []);
  useEffect(() => { refreshList(); }, [refreshList, paperId, paper?.version]);

  const refresh = useCallback(() => {
    if (paperId) api.paper(paperId).then(setPaper).catch(() => {});
  }, [paperId]);

  useEffect(() => { refresh(); }, [refresh]);

  const openPaper = (id: string) => { setPaperId(id); setPaper(null); setTab("parse"); };
  const goHome = () => { setPaperId(null); setPaper(null); };

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

  const NAV: [Tab, string, () => JSX.Element][] = [
    ["parse", "Overview", Icon.overview],
    ["paper", "Paper", Icon.paper],
    ["export", "Export", Icon.download],
  ];

  return (
    <div className="app">
      {/* ------------------------------------------------------- rail -- */}
      <aside className="rail">
        <div className="rail-logo" onClick={goHome}>
          <span className="mark">✳</span> paper.agent
        </div>
        <nav className="rail-nav">
          {paperId && (
            <>
              <div className="rail-group">Workspace</div>
              {NAV.map(([t, label, Ico]) => (
                <button key={t}
                  className={`rail-item ${tab === t && paper ? "active" : ""}`}
                  disabled={!paper}
                  onClick={() => setTab(t)}>
                  <span className="ico"><Ico /></span>
                  <span className="lbl">{label}</span>
                </button>
              ))}
            </>
          )}

          <div className="rail-group">Papers</div>
          {papers.map((p) => (
            <button key={p.id}
              className={`rail-item ${p.id === paperId ? "active" : ""}`}
              onClick={() => openPaper(p.id)}
              title={p.title || p.filename}>
              <span className="ico"><Icon.doc /></span>
              <span className="lbl">{p.title || p.filename}</span>
              <span className="meta">v{p.version}</span>
            </button>
          ))}
          <button className="rail-item" onClick={goHome}>
            <span className="ico"><Icon.plus /></span>
            <span className="lbl">Upload</span>
          </button>
        </nav>
        <div className="rail-foot">
          {health && (
            <span className={`pill ${health.llm ? "ok" : "warn"}`}
              title={health.llm_hint ?? undefined}>
              {health.llm ? `LLM · ${health.llm}` : "no LLM configured"}
            </span>
          )}
          {health && (
            <span className="pill" title="Semantic Scholar API key raises rate limits (optional)">
              S2 key · {health.semantic_scholar_key ? "yes" : "no"}
            </span>
          )}
        </div>
      </aside>

      {/* ---------------------------------------------------- content -- */}
      <div className="content">
        <div className="topbar">
          {paper ? (
            <>
              <span className="crumb">
                {tab === "parse" ? "Overview" : tab === "paper" ? "Paper" : "Export"}
              </span>
              <span className="crumb">/</span>
              <span className="paper-title">{paper.meta.title || paper.filename}</span>
              <span className="crumb">v{paper.version}</span>
            </>
          ) : (
            <span className="crumb"><b>Paper Improvement Agent</b></span>
          )}
          <span className="spacer" />
        </div>

        {!paperId && <div className="page"><Upload onOpen={openPaper} /></div>}

        {paperId && paper && tab === "parse" && (
          <div className="page">
            <div className="page-inner">
              <h1 className="page-title">Overview</h1>
              <p className="page-sub">What the parser found in <strong>{paper.filename}</strong>.</p>
              <ParseView paper={paper} onResolve={() => void startResolve()} resolving={resolving} />
            </div>
          </div>
        )}

        {paperId && paper && tab === "paper" && (
          <Workspace paper={paper} llm={health?.llm ?? null} onPaperRefresh={refresh} />
        )}

        {paperId && paper && tab === "export" && (
          <ExportView paper={paper} onStyleChange={refresh} />
        )}

        {paperId && !paper && (
          <div style={{ padding: 40 }} className="muted"><span className="spin" /> Loading paper…</div>
        )}
      </div>
    </div>
  );
}
