import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type {
  CitePart, EditProposal, Finding, Paper, Reference, RenderedDoc, ReviewRun,
} from "../types";
import { Badge, SourceLine } from "./bits";
import { DiffView } from "./diff";
import { LatexPane } from "./LatexPane";
import { Loading } from "./Loading";
import { ReaderOutline } from "./ReaderOutline";
import { EmptyArt, Icon } from "./icons";

const EXAMPLES = [
  "add more citations to the introduction",
  "make the introduction shorter",
  "tighten the conclusion without losing any citations",
];

const VERDICT_LABEL: Record<string, string> = {
  supports: "✓ supports",
  partial: "◐ partial support",
  does_not_support: "✗ does not support",
  cannot_verify: "? cannot verify",
};

const SEV_TONE: Record<string, string> = { high: "bad", medium: "warn", info: "good" };

function FindingCard({ f, onJump, onCite, citing, citeError }: {
  f: Finding; onJump: (sectionId: string) => void;
  onCite?: (f: Finding) => void; citing?: boolean; citeError?: string | null;
}) {
  // Only a missing-work finding with a real source is actionable: the others
  // are observations about the paper, not works it could cite.
  const canCite = f.type === "missing_work" && !!f.source && !!f.section_id;
  return (
    <div className={`card finding ${f.severity}`}>
      <div className="ftitle">
        <Badge tone={SEV_TONE[f.severity] ?? ""}>{f.type.replace(/_/g, " ")}</Badge>
        {f.title}
      </div>
      {f.section_id && f.section_title && (
        <button className="jump" onClick={() => onJump(f.section_id!)}>
          ↦ {f.section_title}
        </button>
      )}
      {f.claim_text && <blockquote>“{f.claim_text}”</blockquote>}
      {f.verdict && (
        <div className="small">
          <strong>{VERDICT_LABEL[f.verdict] ?? f.verdict}</strong>
          {typeof f.confidence === "number" ? ` (confidence ${f.confidence})` : ""}
          {f.verdict_rationale ? ` — ${f.verdict_rationale}` : ""}
        </div>
      )}
      {!f.verdict && f.detail && <div className="small">{f.detail}</div>}
      {f.evidence_quote && <blockquote className="small">Abstract says: “{f.evidence_quote}”</blockquote>}
      {f.source && <SourceLine s={f.source} />}
      {canCite && onCite && (
        <div className="finding-act">
          <button className="cite-this" disabled={citing}
            onClick={() => onCite(f)}>
            {citing ? "Preparing…" : <><Icon.link size={13} /> Cite this</>}
          </button>
          <span className="small muted">proposes the edit — you still approve it</span>
        </div>
      )}
      {citeError && <div className="error-banner small">{citeError}</div>}
      {f.provenance && (
        <div className="prov">
          provenance: {f.provenance}
          {f.llm_used && !f.provenance.includes(f.llm_used) ? ` · judged by ${f.llm_used}` : ""}
        </div>
      )}
    </div>
  );
}

export function Workspace({ paper, llm, onPaperRefresh }: {
  paper: Paper; llm: string | null; onPaperRefresh: () => void;
}) {
  const [view, setView] = useState<"reader" | "latex">("reader");
  const [panel, setPanel] = useState<"review" | "edit">("review");
  const [doc, setDoc] = useState<RenderedDoc | null>(null);
  const [flashId, setFlashId] = useState<string | null>(null);

  // ---- review state ----
  const [runs, setRuns] = useState<ReviewRun[]>([]);
  const [run, setRun] = useState<ReviewRun | null>(null);
  const [missingWork, setMissingWork] = useState(true);
  const [claimChecks, setClaimChecks] = useState(true);
  const [starting, setStarting] = useState(false);
  const [citing, setCiting] = useState<string | null>(null);       // finding id
  const [citeError, setCiteError] = useState<{ id: string; msg: string } | null>(null);
  const reviewTimer = useRef<number | null>(null);

  // ---- manual in-place editing ----
  const [editingSec, setEditingSec] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [savingSec, setSavingSec] = useState(false);
  const [secError, setSecError] = useState<string | null>(null);

  // ---- select-to-act toolbar (agentic editing scoped to a passage) ----
  const [sel, setSel] = useState<{
    sectionId: string; sectionTitle: string; text: string; x: number; y: number;
  } | null>(null);
  const paneRef = useRef<HTMLDivElement>(null);

  // ---- edit state ----
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [prop, setProp] = useState<EditProposal | null>(null);
  const [proposals, setProposals] = useState<EditProposal[]>([]);
  const [approved, setApproved] = useState<Record<string, boolean>>({});
  const [applyError, setApplyError] = useState<string | null>(null);
  const editTimer = useRef<number | null>(null);

  useEffect(() => {
    setDoc(null);
    api.rendered(paper.id).then(setDoc).catch(() => {});
  }, [paper.id, paper.version, paper.csl_style]);

  const pollReview = useCallback((runId: string) => {
    api.review(paper.id, runId).then((r) => {
      setRun(r);
      setRuns((rs) => [r, ...rs.filter((x) => x.id !== r.id)]);
      if (r.status === "running" || r.status === "pending") {
        reviewTimer.current = window.setTimeout(() => pollReview(runId), 1500);
      }
    }).catch(() => {});
  }, [paper.id]);

  const seedApprovals = (p: EditProposal) => {
    const a: Record<string, boolean> = {};
    p.changes.forEach((c) => { a[c.id] = p.integrity.ok; });
    setApproved(a);
  };

  /** Accept a missing-work finding. The result is a normal proposal, so it
   *  opens the edit panel with a diff to approve — accepting a finding is
   *  not the same as applying it. */
  const citeFinding = useCallback(async (f: Finding) => {
    if (!run) return;
    setCiting(f.id); setCiteError(null);
    try {
      const p = await api.citeFinding(paper.id, run.id, f.id);
      setProp(p);
      setProposals((ps) => [p, ...ps.filter((x) => x.id !== p.id)]);
      seedApprovals(p);
      setPanel("edit");
    } catch (e) {
      setCiteError({ id: f.id, msg: String(e instanceof Error ? e.message : e) });
    } finally { setCiting(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper.id, run]);

  const pollEdit = useCallback((propId: string) => {
    api.proposal(paper.id, propId).then((p) => {
      setProp(p);
      setProposals((ps) => [p, ...ps.filter((x) => x.id !== p.id)]);
      if (p.status === "running") editTimer.current = window.setTimeout(() => pollEdit(propId), 1500);
      else seedApprovals(p);
    }).catch(() => {});
  }, [paper.id]);

  useEffect(() => {
    api.reviews(paper.id).then((rs) => {
      setRuns(rs);
      if (rs.length) {
        setRun(rs[0]);
        if (rs[0].status === "running" || rs[0].status === "pending") pollReview(rs[0].id);
      }
    }).catch(() => {});
    api.proposals(paper.id).then((ps) => {
      setProposals(ps);
      const open = ps.find((p) => p.status === "running" || p.status === "proposed");
      if (open) {
        setProp(open); seedApprovals(open);
        if (open.status === "running") pollEdit(open.id);
      }
    }).catch(() => {});
    return () => {
      if (reviewTimer.current) window.clearTimeout(reviewTimer.current);
      if (editTimer.current) window.clearTimeout(editTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper.id]);

  const refsMap = useMemo(() => {
    const m = new Map<string, Reference>();
    paper.references.forEach((r) => m.set(r.id, r));
    prop?.new_references.forEach((r) => m.set(r.id, r));
    return m;
  }, [paper, prop]);

  const findingsBySection = useMemo(() => {
    const m = new Map<string, Finding[]>();
    (run?.findings ?? []).forEach((f) => {
      if (f.section_id) {
        if (!m.has(f.section_id)) m.set(f.section_id, []);
        m.get(f.section_id)!.push(f);
      }
    });
    return m;
  }, [run]);

  const changesBySection = useMemo(() => {
    const m = new Map<string, EditProposal["changes"][number]>();
    if (prop && prop.status === "proposed") prop.changes.forEach((c) => m.set(c.section_id, c));
    return m;
  }, [prop]);

  // ---- citation → bibliography, and back ----
  /** Scroll an element into view, smoothly for a short hop.
   *  A smooth scroll across a whole bibliography — tens of thousands of
   *  pixels — is both slow to watch and fragile: the browser abandons the
   *  animation when anything else touches the scroller mid-flight, and the
   *  jump silently does nothing. Past a few screens, go straight there; the
   *  flash on arrival is what tells the reader they moved. */
  const scrollHere = (el: Element) => {
    const far = Math.abs(el.getBoundingClientRect().top) > window.innerHeight * 3;
    el.scrollIntoView({ behavior: far ? "auto" : "smooth", block: "center" });
  };

  const [flashBib, setFlashBib] = useState<string[]>([]);
  const [canReturn, setCanReturn] = useState(false);
  const returnTo = useRef<HTMLElement | null>(null);

  const citeTitle = useCallback((refs: string[]) => {
    const names = refs.map((id) => {
      const r = refsMap.get(id);
      return (r?.csl.title as string) || r?.raw_text.slice(0, 80) || id;
    });
    return `${names.join("\n")}\n\nClick to show in the references`;
  }, [refsMap]);

  /** The references sit hundreds of lines below the prose, so a jump that
   *  can't be undone loses the reader's place. Remember where they were and
   *  offer the way back until they navigate somewhere else themselves. */
  const jumpToBib = useCallback((refs: string[], from: HTMLElement) => {
    const target = refs.map((r) => document.getElementById(`bib-${r}`)).find(Boolean);
    if (!target) return;                       // unrenderable ref — nothing to show
    returnTo.current = from;
    setCanReturn(true);
    scrollHere(target);
    setFlashBib(refs);
    window.setTimeout(() => setFlashBib([]), 2400);
  }, []);

  const backToText = useCallback(() => {
    if (returnTo.current) scrollHere(returnTo.current);
    setCanReturn(false);
  }, []);

  const jumpTo = useCallback((sectionId: string) => {
    setView("reader");
    window.setTimeout(() => {
      document.getElementById(`psec-${sectionId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
      setFlashId(sectionId);
      window.setTimeout(() => setFlashId(null), 1800);
    }, 60);
  }, []);

  /** Selection → floating action pill. Position is relative to the pane. */
  const onReaderMouseUp = () => {
    const s = window.getSelection();
    const text = s?.toString().trim() ?? "";
    if (!s || s.isCollapsed || text.length < 8 || text.length > 600) { setSel(null); return; }
    const node = s.anchorNode instanceof Element ? s.anchorNode : s.anchorNode?.parentElement;
    const secEl = node?.closest?.("section[id^='psec-']");
    if (!secEl) { setSel(null); return; }
    const sectionId = secEl.id.replace("psec-", "");
    const title = paper.sections.find((x) => x.id === sectionId)?.title || "this section";
    const rect = s.getRangeAt(0).getBoundingClientRect();
    const pane = paneRef.current?.getBoundingClientRect();
    if (!pane) return;
    setSel({
      sectionId, sectionTitle: title, text,
      x: Math.min(Math.max(rect.left + rect.width / 2 - pane.left, 150), pane.width - 150),
      y: Math.max(rect.top - pane.top, 46),
    });
  };

  const runEditWith = (cmd: string) => {
    setSel(null);
    window.getSelection()?.removeAllRanges();
    setPanel("edit");
    setCommand(cmd);
    setBusy(true); setApplyError(null);
    api.startEdit(paper.id, cmd)
      .then(({ proposal_id }) => pollEdit(proposal_id))
      .catch((e) => setApplyError(String(e instanceof Error ? e.message : e)))
      .finally(() => setBusy(false));
  };

  const quoteSel = (t: string) => `“${t.length > 160 ? t.slice(0, 160) + "…" : t}”`;

  const beginSecEdit = (sectionId: string) => {
    const raw = paper.sections.find((s) => s.id === sectionId)?.content ?? "";
    setEditingSec(sectionId);
    setDraft(raw);
    setSecError(null);
  };

  const saveSecEdit = async () => {
    if (!editingSec) return;
    setSavingSec(true); setSecError(null);
    try {
      await api.editSection(paper.id, editingSec, draft, paper.version);
      setEditingSec(null);
      onPaperRefresh();
    } catch (e) {
      setSecError(String(e instanceof Error ? e.message : e));
    } finally { setSavingSec(false); }
  };

  const startReview = async () => {
    setStarting(true);
    try {
      const { run_id } = await api.startReview(paper.id, {
        missing_work: missingWork, claim_checks: claimChecks,
      });
      pollReview(run_id);
    } finally { setStarting(false); }
  };

  const runEdit = async () => {
    if (!command.trim()) return;
    setBusy(true); setApplyError(null);
    try {
      const { proposal_id } = await api.startEdit(paper.id, command.trim());
      pollEdit(proposal_id);
    } catch (e) {
      setApplyError(String(e instanceof Error ? e.message : e));
    } finally { setBusy(false); }
  };

  const applyEdit = async () => {
    if (!prop) return;
    setApplyError(null);
    const ids = Object.entries(approved).filter(([, v]) => v).map(([k]) => k);
    try {
      await api.applyProposal(paper.id, prop.id, ids);
      onPaperRefresh();
      pollEdit(prop.id);
    } catch (e) {
      setApplyError(String(e instanceof Error ? e.message : e));
    }
  };

  const rejectEdit = async () => {
    if (!prop) return;
    await api.rejectProposal(paper.id, prop.id);
    pollEdit(prop.id);
  };

  const reviewRunning = run != null && (run.status === "running" || run.status === "pending");
  const editRunning = prop?.status === "running";
  const nApproved = Object.values(approved).filter(Boolean).length;

  return (
    <div className="wsplit">
      {/* ------------------------------------------------ paper (left) -- */}
      <div className="paper-pane" ref={paneRef}>
        <div className="paper-pane-head">
          <div className="seg">
            <button className={view === "reader" ? "on" : ""} onClick={() => setView("reader")}>Paper</button>
            <button className={view === "latex" ? "on" : ""} onClick={() => setView("latex")}>LaTeX</button>
          </div>
          <span className="small muted">
            {view === "reader"
              ? doc ? <>{doc.style} · v{paper.version}</> : "rendering…"
              : "rebuilt live"}
          </span>
        </div>

        {sel && (
          <div className="sel-bar" style={{ left: sel.x, top: sel.y }}
            onMouseDown={(e) => e.preventDefault()}>
            <button onClick={() => runEditWith(
              `add citations supporting this passage in "${sel.sectionTitle}": ${quoteSel(sel.text)}`)}>
              <Icon.link size={13} /> Cite
            </button>
            <button onClick={() => runEditWith(
              `shorten this passage in "${sel.sectionTitle}" without losing citations: ${quoteSel(sel.text)}`)}>
              <Icon.spark size={13} /> Shorten
            </button>
            <button onClick={() => runEditWith(
              `improve the clarity of this passage in "${sel.sectionTitle}": ${quoteSel(sel.text)}`)}>
              <Icon.pencil size={13} /> Improve
            </button>
            <button onClick={() => {
              setPanel("edit");
              setCommand(`in "${sel.sectionTitle}", ${quoteSel(sel.text)}: `);
              setSel(null);
            }}>
              Ask…
            </button>
          </div>
        )}

        {view === "latex" ? <LatexPane paper={paper} onChanged={onPaperRefresh} /> : (
          <div className="sheet-scroll" onMouseUp={onReaderMouseUp}
            onScroll={() => setSel(null)}>
            {!doc ? (
              <Loading label="Rendering citations with citeproc…" />
            ) : (
              <div className="reader-layout">
              <article className="sheet reader">
                <h1 style={{ fontSize: 25, marginTop: 0 }}>{paper.meta.title}</h1>
                {paper.meta.authors.length > 0 && (
                  <div className="muted">{paper.meta.authors.join(", ")}</div>
                )}
                {doc.sections.map((s) => {
                  const change = changesBySection.get(s.id);
                  const secFindings = findingsBySection.get(s.id) ?? [];
                  return (
                    <section key={s.id} id={`psec-${s.id}`}
                      className={flashId === s.id ? "flash" : ""}>
                      <div className="sec-head">
                        {s.kind === "abstract"
                          ? <h2>Abstract</h2>
                          : (s.level === 1 ? <h2>{s.title}</h2> : <h3>{s.title}</h3>)}
                        {!change && editingSec !== s.id && (
                          <button className="sec-edit-btn" title="Edit this section"
                            onClick={() => beginSecEdit(s.id)}>
                            <Icon.pencil size={13} /> Edit
                          </button>
                        )}
                      </div>

                      {secFindings.length > 0 && (
                        <div className="finding-inline">
                          {secFindings.map((f) => (
                            <button key={f.id} className={`fdot ${f.severity}`}
                              title={f.title}
                              onClick={() => setPanel("review")}>
                              {f.type === "missing_work" ? "missing work" : f.verdict ? (VERDICT_LABEL[f.verdict] ?? f.verdict) : f.type.replace(/_/g, " ")}
                            </button>
                          ))}
                        </div>
                      )}

                      {editingSec === s.id ? (
                        <div className="sec-editor">
                          <textarea value={draft} autoFocus
                            onChange={(e) => setDraft(e.target.value)} />
                          {secError && <div className="error-banner" style={{ marginTop: 8 }}>{secError}</div>}
                          <div className="sec-editor-bar">
                            <span className="hint">
                              Keep <code>[[citep:…]]</code> tokens as-is or delete them.
                            </span>
                            <button className="ghost" disabled={savingSec}
                              onClick={() => setEditingSec(null)}>Cancel</button>
                            <button className="primary" disabled={savingSec}
                              onClick={() => void saveSecEdit()}>
                              {savingSec ? "Saving…" : "Save"}
                            </button>
                          </div>
                        </div>
                      ) : change ? (
                        <div className="inline-change">
                          <div className="inline-change-head">
                            <Badge tone="accent">proposed edit</Badge>
                            <span className="small muted">
                              citations {change.citations_before.length} → {change.citations_after.length}
                            </span>
                            <label>
                              <input type="checkbox" checked={approved[change.id] ?? false}
                                onChange={(e) => setApproved((a) => ({ ...a, [change.id]: e.target.checked }))} />
                              approve
                            </label>
                          </div>
                          {change.rationale && <div className="small muted" style={{ margin: "2px 0 8px" }}>{change.rationale}</div>}
                          <DiffView before={change.before} after={change.after} refs={refsMap} />
                        </div>
                      ) : (
                        // paragraphs is the current shape; the html split is
                        // the fallback for a response from an older backend.
                        (s.paragraphs ?? s.html.split("\n\n")
                          .map((t): CitePart[] => [{ t }]))
                          .map((parts, i) => (
                            <p key={i}>
                              {parts.map((part, j) => part.refs
                                ? <button key={j} className="cite-label"
                                    title={citeTitle(part.refs)}
                                    onClick={(e) => jumpToBib(part.refs!, e.currentTarget)}>
                                    {part.label}
                                  </button>
                                : <span key={j}>{part.t}</span>)}
                            </p>
                          ))
                      )}

                      {(paper.floats ?? [])
                        .filter((f) => f.section_id === s.id)
                        .map((f) => (
                          <figure key={f.id} className={`float float-${f.kind}`}>
                            <div className="float-head">
                              <Badge tone="accent">{f.kind}</Badge>
                              <span className="small muted">page {f.page + 1}</span>
                              <span className="small muted float-note">
                                text preserved · layout not reconstructed
                              </span>
                            </div>
                            <pre className="float-body">{f.text}</pre>
                            {f.caption && <figcaption>{f.caption}</figcaption>}
                          </figure>
                        ))}
                    </section>
                  );
                })}
                <h2 id="bib-top">References</h2>
                {doc.bibliography.map((b) => (
                  <div key={b.ref_id} id={`bib-${b.ref_id}`}
                    className={`bib-entry ${b.raw_fallback ? "raw" : ""} ${flashBib.includes(b.ref_id) ? "flash-bib" : ""}`}>
                    <span className="bib-id">{b.ref_id}</span>
                    {b.formatted}
                    {b.raw_fallback && <span className="small"> — unparsed, raw text shown</span>}
                  </div>
                ))}
              </article>

              <ReaderOutline sections={doc.sections} onJump={jumpTo} />
              </div>
            )}
            {canReturn && (
              <button className="bib-return" onClick={backToText}>
                ↑ Back to the text
              </button>
            )}
          </div>
        )}

        {prop && prop.status === "proposed" && view === "reader" && (
          <div className="apply-bar">
            <span className={`integrity ${prop.integrity.ok ? "ok" : "fail"}`}
              title={prop.integrity.summary}>
              {prop.integrity.ok
                ? "Citations intact"
                : <><Icon.alert size={14} /> {prop.integrity.violations.length} violation
                  {prop.integrity.violations.length === 1 ? "" : "s"}</>}
            </span>
            <span className="spacer" />
            <button className="ghost" onClick={() => void rejectEdit()}>Reject</button>
            <button className="primary" onClick={() => void applyEdit()}
              disabled={!prop.integrity.ok || nApproved === 0}>
              <Icon.check size={15} /> Apply {nApproved}
            </button>
          </div>
        )}
      </div>

      {/* ------------------------------------------------- panel (right) -- */}
      <aside className="side-panel">
        <div className="side-tabs">
          <button className={panel === "review" ? "on" : ""} onClick={() => setPanel("review")}>
            <Icon.search size={14} /> Review{run ? ` (${run.findings.length})` : ""}
          </button>
          <button className={panel === "edit" ? "on" : ""} onClick={() => setPanel("edit")}>
            <Icon.spark size={14} /> Edit
          </button>
        </div>

        {panel === "review" && (
          <div className="side-body">
            {!llm && (
              <div className="notice small">
                <Icon.alert size={14} /> No LLM — claim verdicts disabled.
              </div>
            )}
            <div className="runbar">
              <button className="primary" onClick={() => void startReview()} disabled={reviewRunning || starting}>
                {reviewRunning ? <><span className="spin" />Running…</> : <><Icon.search size={15} /> Run review</>}
              </button>
              {runs.length > 1 && (
                <select value={run?.id ?? ""} onChange={(e) => {
                  const r = runs.find((x) => x.id === e.target.value);
                  if (r) setRun(r);
                }}>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      {new Date(r.started_at * 1000).toLocaleTimeString()} — {r.status} ({r.findings.length})
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="checkrow">
              <label className="checklabel">
                <input type="checkbox" checked={missingWork} onChange={(e) => setMissingWork(e.target.checked)} />
                missing work
              </label>
              <label className="checklabel">
                <input type="checkbox" checked={claimChecks} onChange={(e) => setClaimChecks(e.target.checked)} />
                claim–citation checks
              </label>
            </div>

            {run && (reviewRunning || run.progress.length > 0) && (
              <div className="progress-log">
                {run.progress.slice(-14).map((p, i) => <div key={i}>{p}</div>)}
                {reviewRunning && <div><span className="spin" /> working…</div>}
              </div>
            )}
            {run?.error && <div className="error-banner">{run.error}</div>}

            {run && run.findings.map((f) => (
              <FindingCard key={f.id} f={f} onJump={jumpTo} onCite={citeFinding}
                citing={citing === f.id}
                citeError={citeError?.id === f.id ? citeError.msg : null} />
            ))}
            {run && run.status === "done" && run.findings.length === 0 && (
              <div className="empty"><EmptyArt kind="review" /><p>No findings.</p></div>
            )}
            {!run && (
              <div className="empty">
                <EmptyArt kind="review" />
                <p>Checks citations against Semantic Scholar &amp; OpenAlex.</p>
              </div>
            )}
          </div>
        )}

        {panel === "edit" && (
          <div className="side-body">
            {!llm && (
              <div className="notice small">
                <Icon.alert size={14} /> Needs an LLM key to edit.
              </div>
            )}
            <div className="cmd">
              <input
                value={command}
                placeholder="What should change?"
                onChange={(e) => setCommand(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void runEdit(); }}
              />
              <button className="primary" onClick={() => void runEdit()} disabled={busy || editRunning}>
                {editRunning ? <><span className="spin" />…</> : <><Icon.spark size={15} /> Propose</>}
              </button>
            </div>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} onClick={() => setCommand(ex)}>{ex}</button>
              ))}
            </div>

            {applyError && <div className="error-banner">{applyError}</div>}

            {prop && (
              <div className="prop-summary">
                <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                  <strong className="small">“{prop.command}”</strong>
                  <Badge tone={prop.status === "applied" ? "good" : prop.status === "failed" ? "bad" : prop.status === "proposed" ? "accent" : ""}>
                    {prop.status}
                  </Badge>
                </div>
                {proposals.length > 1 && (
                  <select value={prop.id} onChange={(e) => {
                    const p = proposals.find((x) => x.id === e.target.value);
                    if (p) { setProp(p); seedApprovals(p); }
                  }}>
                    {proposals.map((p) => (
                      <option key={p.id} value={p.id}>“{p.command.slice(0, 38)}” — {p.status}</option>
                    ))}
                  </select>
                )}
                {prop.plan && <p className="small" style={{ margin: "6px 0 2px" }}><strong>Plan:</strong> {prop.plan}</p>}
                {prop.steps.length > 0 && (
                  <ul className="step-log">
                    {prop.steps.map((s, i) => (
                      <li key={i}><span className="k">{s.kind}</span>{s.text}</li>
                    ))}
                    {editRunning && <li><span className="spin" /> …</li>}
                  </ul>
                )}
                {prop.error && <div className="error-banner">{prop.error}</div>}

                {prop.status === "proposed" && prop.changes.length > 0 && (
                  <div className="small" style={{ margin: "8px 0" }}>
                    <span className="muted">{prop.changes.length} diff{prop.changes.length === 1 ? "" : "s"} inline — approve there.</span>
                    {prop.changes.map((c) => (
                      <button key={c.id} className="jump" onClick={() => jumpTo(c.section_id)}>
                        ↦ {c.section_title}
                      </button>
                    ))}
                  </div>
                )}

                {prop.new_references.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <h3 style={{ margin: "0 0 6px" }}><Icon.link /> New sources ({prop.new_references.length})</h3>
                    {prop.citation_adds.map((a) => {
                      const r = prop.new_references.find((x) => x.id === a.ref_id);
                      return (
                        <div key={a.ref_id} className="card" style={{ marginBottom: 8, padding: "10px 12px" }}>
                          {r && r.resolution.source_url && (
                            <SourceLine s={{
                              api: a.api, api_id: r.resolution.source_id ?? "",
                              title: String(r.csl.title ?? r.parsed.title ?? "?"),
                              year: r.parsed.year ?? null, authors: r.parsed.authors,
                              venue: r.parsed.container ?? null, doi: r.resolution.doi ?? null,
                              url: a.source_url, abstract: r.resolution.abstract ?? null,
                              cited_by_count: null,
                            }} />
                          )}
                          <div className="small muted">why: {a.reason}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

          </div>
        )}
      </aside>
    </div>
  );
}
