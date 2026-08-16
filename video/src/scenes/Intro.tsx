import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Chip, SceneShell, Typewriter } from "../components";
import { theme } from "../theme";

export const Title: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  const s2 = spring({ frame: frame - 14, fps, config: { damping: 200 } });
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
            fontFamily: theme.mono,
            fontSize: 24,
            letterSpacing: 6,
            textTransform: "uppercase",
            color: theme.good,   /* lime is a surface, not text — use the deep lime ink */
            opacity: s,
          }}
        >
          Feature tour
        </div>
        <div
          style={{
            fontSize: 118,
            fontWeight: 500,
            letterSpacing: -4,
            marginTop: 22,
            opacity: s,
            transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`,
          }}
        >
          Paper{" "}
          {/* The one place lime behaves the way it does in the app: a filled
              surface with ink on top, never coloured text. */}
          <span
            style={{
              background: theme.accent,
              color: theme.accentInk,
              padding: "0 18px",
              borderRadius: theme.radiusInner,
            }}
          >
            Improvement
          </span>{" "}
          Agent
        </div>
        <div
          style={{
            fontSize: 34,
            color: theme.textDim,
            marginTop: 24,
            maxWidth: 1250,
            lineHeight: 1.45,
            opacity: s2,
          }}
        >
          Upload a research PDF, see exactly how it parsed, get a peer review
          grounded in real academic search, edit it with natural language, and
          export LaTeX — without ever losing a citation.
        </div>
        <div
          style={{
            marginTop: 46,
            fontSize: 30,
            color: theme.textFaint,
          }}
        >
          <Typewriter
            delay={40}
            cps={30}
            text="upload → parse → read → review → edit → export"
            style={{ color: theme.green, fontSize: 30 }}
          />
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 52 }}>
          <Chip delay={70}>FastAPI + Python 3.11</Chip>
          <Chip delay={78} color={theme.purple}>
            React + TypeScript
          </Chip>
          <Chip delay={86} color={theme.green}>
            OpenAlex · Semantic Scholar
          </Chip>
          <Chip delay={94} color={theme.amber}>
            CSL-JSON · citeproc
          </Chip>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

const STEPS = [
  { n: "1", label: "Upload & parse", note: "5-stage deterministic pipeline" },
  { n: "2", label: "Read", note: "citeproc-rendered, clickable citations" },
  { n: "3", label: "Peer review", note: "real sources, verified quotes" },
  { n: "4", label: "Edit", note: "typed ops, diffs you approve" },
  { n: "5", label: "Export", note: "LaTeX project zip" },
];

export const Overview: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: 110, justifyContent: "center" }}>
        <div style={{ fontSize: 64, fontWeight: 500, letterSpacing: -1.5 }}>
          Five screens, one canonical document
        </div>
        <div
          style={{
            fontSize: 30,
            color: theme.textDim,
            marginTop: 16,
            maxWidth: 1300,
          }}
        >
          Every screen reads and writes the same{" "}
          <span style={{ fontFamily: theme.mono, color: theme.green }}>
            PaperDocument
          </span>
          . References are CSL-JSON from the moment they are parsed to the
          moment they are exported.
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            gap: 18,
            marginTop: 70,
          }}
        >
          {STEPS.map((s, i) => {
            const sp = spring({
              frame: frame - 18 - i * 14,
              fps,
              config: { damping: 200 },
            });
            return (
              <React.Fragment key={s.n}>
                <div
                  style={{
                    flex: 1,
                    background: theme.panel,
                    border: `1px solid ${theme.panelLine}`,
                    borderRadius: 18,
                    padding: 30,
                    opacity: sp,
                    transform: `translateY(${interpolate(sp, [0, 1], [30, 0])}px)`,
                  }}
                >
                  <div
                    style={{
                      fontFamily: theme.mono,
                      fontSize: 46,
                      color: theme.good,   /* lime is a surface, not text — use the deep lime ink */
                      fontWeight: 500,
                    }}
                  >
                    {s.n}
                  </div>
                  <div
                    style={{ fontSize: 32, fontWeight: 500, marginTop: 12 }}
                  >
                    {s.label}
                  </div>
                  <div
                    style={{
                      fontSize: 23,
                      color: theme.textFaint,
                      marginTop: 12,
                      lineHeight: 1.4,
                    }}
                  >
                    {s.note}
                  </div>
                </div>
                {i < STEPS.length - 1 ? (
                  <div
                    style={{
                      alignSelf: "center",
                      color: theme.good,   /* lime is a surface, not text — use the deep lime ink */
                      fontSize: 34,
                      opacity: spring({
                        frame: frame - 26 - i * 14,
                        fps,
                        config: { damping: 200 },
                      }),
                    }}
                  >
                    ›
                  </div>
                ) : null}
              </React.Fragment>
            );
          })}
        </div>

        <div
          style={{
            marginTop: 64,
            display: "flex",
            gap: 14,
            flexWrap: "wrap",
          }}
        >
          <Chip delay={100} color={theme.green}>
            no LLM in the parser
          </Chip>
          <Chip delay={108} color={theme.purple}>
            no fabricated sources
          </Chip>
          <Chip delay={116} color={theme.amber}>
            no silent citation loss
          </Chip>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};
