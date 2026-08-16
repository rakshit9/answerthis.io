import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  Card,
  Chip,
  Lines,
  Mono,
  SceneHeader,
  SceneShell,
  Typewriter,
} from "../components";
import { theme } from "../theme";

const MODULES = [
  { n: "parsing/", d: "A–E pipeline: extract → floats → structure → reflist → refparse → intext", c: theme.accent },
  { n: "models/", d: "PaperDocument (token-bearing sections), Reference (CSL-JSON), findings, proposals", c: theme.green },
  { n: "external/", d: "OpenAlex + Semantic Scholar clients, disk cache, resolution ladder", c: theme.purple },
  { n: "cslproc/", d: "citeproc rendering + vendored .csl styles", c: theme.amber },
  { n: "llm/", d: "pluggable providers — OpenAI, Gemini, mock", c: theme.accent },
  { n: "review/", d: "claim–citation checks + missing-work search", c: theme.green },
  { n: "agent/", d: "planner → typed ops → integrity checker → apply", c: theme.purple },
  { n: "export/", d: "LaTeX / BibTeX / Markdown / provenance", c: theme.amber },
];

export const Architecture: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: "80px 100px" }}>
        <SceneHeader
          step="Architecture"
          title="One FastAPI process, eight modules"
          subtitle="On-disk JSON store, no database, no auth — everything above is one deployable."
        />
        <div
          style={{
            marginTop: 46,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
          }}
        >
          {MODULES.map((m, i) => {
            const s = spring({
              frame: frame - 24 - i * 10,
              fps,
              config: { damping: 200 },
            });
            return (
              <div
                key={m.n}
                style={{
                  border: `1px solid ${theme.panelLine}`,
                  background: theme.panel,
                  borderRadius: 14,
                  padding: "20px 24px",
                  opacity: s,
                  transform: `translateY(${interpolate(s, [0, 1], [20, 0])}px)`,
                }}
              >
                <div
                  style={{
                    fontFamily: theme.mono,
                    fontSize: 28,
                    color: m.c,
                    marginBottom: 8,
                  }}
                >
                  backend/app/{m.n}
                </div>
                <div style={{ fontSize: 23, color: theme.textDim, lineHeight: 1.4 }}>
                  {m.d}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 34, display: "flex", gap: 14 }}>
          <Chip delay={130} size={24} color={theme.green}>
            116 pytest tests, no network required
          </Chip>
          <Chip delay={140} size={24}>
            React + TS frontend, Vite dev proxy
          </Chip>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

export const RunIt: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "80px 100px" }}>
      <SceneHeader step="Run it" title="Two commands, or one container" />
      <div style={{ display: "flex", gap: 34, marginTop: 44 }}>
        <Card title="Local" delay={20} style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: theme.mono,
              fontSize: 24,
              lineHeight: 1.85,
              color: theme.textDim,
            }}
          >
            <div>
              <span style={{ color: theme.textFaint }}>$ </span>uvicorn
              app.main:app --port 8000
            </div>
            <div>
              <span style={{ color: theme.textFaint }}>$ </span>npm run dev{" "}
              <span style={{ color: theme.textFaint }}>· :5173</span>
            </div>
            <div style={{ marginTop: 14, color: theme.green }}>
              <Typewriter
                delay={40}
                cps={20}
                text="$ docker compose up --build"
                style={{ fontSize: 24, color: theme.green }}
              />
            </div>
          </div>
        </Card>
        <Card title="Keys — all optional" delay={34} accent={theme.amber} style={{ flex: 1.25 }}>
          <Lines
            delay={44}
            fontSize={24}
            items={[
              <>
                <Mono color={theme.amber}>OPENAI_API_KEY</Mono> /{" "}
                <Mono color={theme.amber}>GEMINI_API_KEY</Mono> — without one,
                parsing, rendering, search and export still work
              </>,
              <>
                <Mono color={theme.amber}>S2_API_KEY</Mono> — shared pool works,
                just slower
              </>,
              <>
                <Mono color={theme.amber}>OPENALEX_MAILTO</Mono> — polite pool
              </>,
              <>
                <Mono color={theme.green}>GET /api/health</Mono> — what the app
                actually has right now
              </>,
            ]}
          />
        </Card>
      </div>
      <div style={{ marginTop: 32 }}>
        <Card title="Docs" delay={110} accent={theme.purple}>
          <Lines
            delay={118}
            fontSize={24}
            bullet="›"
            items={[
              <>
                <Mono color={theme.purple}>docs/system-design.md</Mono> — the
                pipeline, the IR, how a command becomes actions
              </>,
              <>
                <Mono color={theme.purple}>docs/limitations.md</Mono> — known
                gaps, honestly listed
              </>,
              <>
                <Mono color={theme.purple}>docs/ai-use-and-verification.md</Mono>{" "}
                — where AI was used and what was checked by hand
              </>,
            ]}
          />
        </Card>
      </div>
    </AbsoluteFill>
  </SceneShell>
);

export const Outro: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: 84,
            fontWeight: 500,
            letterSpacing: -2.5,
            opacity: s,
            transform: `translateY(${interpolate(s, [0, 1], [22, 0])}px)`,
          }}
        >
          Real sources. Real citations.
          <br />
          <span style={{ color: theme.good }}>Nothing lost in the edit.</span>
        </div>
        <div
          style={{
            marginTop: 42,
            fontSize: 30,
            color: theme.textDim,
            maxWidth: 1150,
            lineHeight: 1.5,
          }}
        >
          Parse → read → review → edit → export, with a citation-integrity
          checker between the model and your paper.
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 50 }}>
          <Chip delay={40}>PaperImprovementAgent</Chip>
          <Chip delay={50} color={theme.green}>
            localhost:8000
          </Chip>
          <Chip delay={60} color={theme.purple}>
            made with Remotion
          </Chip>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};
