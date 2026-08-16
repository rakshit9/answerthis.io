import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ParseJob } from "../types";
import { ParseScene } from "./ParseScene";
import { Icon } from "./icons";

/** Live parse: polls the backend's own stage events and renders them
 *  alongside a scene that reshapes as each stage completes. */
export function ParsingView({ paperId, filename, onDone, onFailed }: {
  paperId: string; filename: string;
  onDone: () => void; onFailed: (msg: string) => void;
}) {
  const [job, setJob] = useState<ParseJob | null>(null);
  const timer = useRef<number | null>(null);
  // Held in refs so the poll loop depends only on paperId — otherwise every
  // parent re-render would tear down and restart polling mid-parse.
  const cbs = useRef({ onDone, onFailed });
  cbs.current = { onDone, onFailed };

  useEffect(() => {
    let alive = true;
    const tick = () => {
      api.parseStatus(paperId).then((j) => {
        if (!alive) return;
        setJob(j);
        if (j.status === "done") {
          timer.current = window.setTimeout(() => cbs.current.onDone(), 700);
          return;
        }
        if (j.status === "failed") {
          cbs.current.onFailed(j.error ?? "Parsing failed.");
          return;
        }
        timer.current = window.setTimeout(tick, 250);
      }).catch(() => { if (alive) timer.current = window.setTimeout(tick, 500); });
    };
    tick();
    return () => {
      alive = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [paperId]);

  const stages = job?.stages ?? [];
  const events = job?.events ?? [];
  const doneKeys = events.map((e) => e.key);
  // scene index = how far the algorithm has actually got
  const stageIndex = job?.status === "done" ? stages.length - 1 : doneKeys.length - 1;

  return (
    <div className="parsing">
      <ParseScene stageIndex={stageIndex} running={job?.status === "running"} />

      <div className="parsing-panel">
        <div className="parsing-head">
          <span className="eyebrow">
            {job?.status === "done" ? "Parsed" : "Parsing"}
          </span>
          <h1>{filename}</h1>
          <div className="parsing-progress">
            <i style={{ width: `${Math.round((doneKeys.length / Math.max(1, stages.length)) * 100)}%` }} />
          </div>
        </div>

        <ol className="stage-list">
          {stages.map((s) => {
            const ev = events.find((e) => e.key === s.key);
            const active = job?.current === s.key;
            return (
              <li key={s.key}
                className={`stage ${ev ? "done" : active ? "active" : "todo"}`}>
                <span className="stage-key">{s.key}</span>
                <span className="stage-body">
                  <span className="stage-label">{s.label}</span>
                  {ev && <span className="stage-detail">{ev.text.replace(/^[A-E]'?\.\s*/, "")}</span>}
                </span>
                <span className="stage-mark">
                  {ev ? <Icon.check size={14} />
                    : active ? <span className="stage-live" />
                      : <span className="dot" />}
                </span>
              </li>
            );
          })}
        </ol>

        {job?.status === "done" && (
          <div className="parsing-done"><Icon.check size={15} /> Opening…</div>
        )}
      </div>
    </div>
  );
}
