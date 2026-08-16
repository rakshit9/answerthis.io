import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Health, Paper } from "./types";
import { Upload } from "./components/Upload";
import { ParsingView } from "./components/ParsingView";
import { ParseView } from "./components/ParseView";
import { Workspace } from "./components/Workspace";
import { ExportView } from "./components/ExportView";
import { PaperPicker } from "./components/PaperPicker";
import { Icon } from "./components/icons";

type Tab = "parse" | "paper" | "export";

/** The open paper lives in the URL. Without this a refresh — or the dev
 *  server reloading — drops you back on the upload screen with no route
 *  back to a paper you already parsed, since papers are only reachable by
 *  uploading them. It also makes a paper linkable. */
const paperIdInUrl = () => new URLSearchParams(window.location.search).get("paper");

export default function App() {
  const [paperId, setPaperId] = useState<string | null>(paperIdInUrl);
  const [paper, setPaper] = useState<Paper | null>(null);
  const [tab, setTab] = useState<Tab>("parse");
  const [health, setHealth] = useState<Health | null>(null);
  const [parsing, setParsing] = useState<{ id: string; filename: string } | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);
  const resolveTimer = useRef<number | null>(null);

  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);

  const refresh = useCallback(() => {
    // A stale ?paper= (deleted data dir, wrong backend) must not strand the
    // app on a blank workspace — fall back to the upload screen.
    if (paperId) api.paper(paperId).then(setPaper).catch(() => setPaperId(null));
  }, [paperId]);

  useEffect(() => { refresh(); }, [refresh]);

  // Keep the address bar in step, and follow back/forward.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (paperId) url.searchParams.set("paper", paperId);
    else url.searchParams.delete("paper");
    if (url.toString() !== window.location.href)
      window.history.pushState({}, "", url);
  }, [paperId]);

  useEffect(() => {
    const onPop = () => setPaperId(paperIdInUrl());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const openPaper = useCallback((id: string) => {
    setParsing(null); setPaperId(id); setPaper(null); setTab("parse");
  }, []);
  const goHome = () => { setParsing(null); setPaperId(null); setPaper(null); };

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

  const NAV: [Tab, string, (p?: { size?: number }) => JSX.Element][] = [
    ["parse", "Overview", Icon.overview],
    ["paper", "Paper — review & edit", Icon.paper],
    ["export", "Export", Icon.download],
  ];

  const inWorkspace = !!paperId && !parsing;

  const statusPills = health && (
    <>
      <span className={`pill ${health.llm ? "ok" : "warn"}`} title={health.llm_hint ?? undefined}>
        {health.llm ? `LLM · ${health.llm}` : "no LLM configured"}
      </span>
      <span className="pill" title="Semantic Scholar API key raises rate limits (optional)">
        S2 · {health.semantic_scholar_key ? "yes" : "no"}
      </span>
    </>
  );

  return (
    <div className="app">
      {/* Floating dock — only inside a paper's workspace. The landing and
          the live-parse screens run full-bleed with just a floating mark. */}
      {inWorkspace && (
        <nav className="dock">
          <button className="dock-logo" title="paper.agent — home" onClick={goHome}>✳</button>
          <div className="dock-group">
            {NAV.map(([t, label, Ico]) => (
              <button key={t}
                className={`dock-btn ${tab === t && paper ? "active" : ""}`}
                disabled={!paper} title={label}
                onClick={() => setTab(t)}>
                <Ico size={17} />
              </button>
            ))}
          </div>
          <div className="dock-sep" />
          <button className="dock-btn" title="Upload a new paper" onClick={goHome}>
            <Icon.plus size={17} />
          </button>
          <span className={`dock-dot ${health?.llm ? "ok" : "warn"}`}
            title={health?.llm ? `LLM · ${health.llm} — S2 key · ${health.semantic_scholar_key ? "yes" : "no"}`
              : health?.llm_hint ?? "no LLM configured"} />
        </nav>
      )}

      {!inWorkspace && (
        <div className="float-brand" onClick={goHome}>
          <span className="mark">✳</span> paper.agent
        </div>
      )}
      {!inWorkspace && !parsing && <div className="float-status">{statusPills}</div>}

      <div className={`content ${inWorkspace ? "with-dock" : ""}`}>
        {inWorkspace && paper && (
          <div className="topbar">
            <span className="crumb">
              {tab === "parse" ? "Overview" : tab === "paper" ? "Paper" : "Export"}
            </span>
            <span className="crumb">/</span>
            <PaperPicker
              current={{
                id: paper.id,
                title: paper.meta.title || paper.filename,
                version: paper.version,
              }}
              onPick={openPaper}
              onUpload={goHome} />
            <span className="crumb">v{paper.version}</span>
            <span className="spacer" />
          </div>
        )}

        {parsing && (
          <ParsingView
            paperId={parsing.id}
            filename={parsing.filename}
            onDone={() => openPaper(parsing.id)}
            onFailed={(msg) => { setParsing(null); setParseError(msg); }}
          />
        )}

        {!parsing && !paperId && (
          <div className="page landing">
            {parseError && (
              <div className="error-banner" style={{ maxWidth: 620, margin: "0 auto 18px" }}>
                {parseError}
              </div>
            )}
            <Upload
              onParsing={(id, filename) => { setParseError(null); setParsing({ id, filename }); }} />
          </div>
        )}

        {inWorkspace && paper && tab === "parse" && (
          <div className="page">
            <div className="page-inner">
              <h1 className="page-title">Overview</h1>
              <p className="page-sub">What the parser found in <strong>{paper.filename}</strong>.</p>
              <ParseView paper={paper} onResolve={() => void startResolve()} resolving={resolving} />
            </div>
          </div>
        )}

        {inWorkspace && paper && tab === "paper" && (
          <Workspace paper={paper} llm={health?.llm ?? null} onPaperRefresh={refresh} />
        )}

        {inWorkspace && paper && tab === "export" && (
          <ExportView paper={paper} onStyleChange={refresh} />
        )}

        {inWorkspace && !paper && (
          <div style={{ padding: 40 }} className="muted"><span className="spin" /> Loading paper…</div>
        )}
      </div>
    </div>
  );
}
