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
  Shot,
  Typewriter,
} from "../components";
import { theme } from "../theme";

export const EditCommand: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const flow = [
    { k: "PLAN", v: "planner turns the sentence into typed operations", c: theme.accent },
    { k: "OPS", v: "find_citations · rewrite_section — searched against real APIs", c: theme.purple },
    { k: "DRAFT", v: "LLM rewrite, retried until citation tokens survive", c: theme.amber },
    { k: "CHECK", v: "integrity checker compares tokens before vs after", c: theme.green },
  ];
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: "70px 90px" }}>
        <SceneHeader
          step="Step 4 · Edit"
          title="Say what you want changed"
        />
        <div
          style={{
            marginTop: 28,
            border: `1px solid ${theme.panelLine}`,
            background: theme.panel,
            borderRadius: 14,
            padding: "22px 26px",
            fontSize: 32,
            maxWidth: 1420,
          }}
        >
          <Typewriter
            delay={16}
            cps={24}
            text="add more citations to the introduction"
            style={{ fontSize: 32, color: theme.text }}
          />
        </div>

        <div style={{ display: "flex", gap: 48, marginTop: 38 }}>
          <div style={{ width: 760, flexShrink: 0 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {flow.map((f, i) => {
                const s = spring({
                  frame: frame - 70 - i * 20,
                  fps,
                  config: { damping: 200 },
                });
                return (
                  <div
                    key={f.k}
                    style={{
                      display: "flex",
                      gap: 20,
                      alignItems: "center",
                      padding: "16px 22px",
                      borderRadius: 12,
                      border: `1px solid ${f.c}44`,
                      background: `${f.c}0d`,
                      opacity: s,
                      transform: `translateY(${interpolate(s, [0, 1], [18, 0])}px)`,
                    }}
                  >
                    <div
                      style={{
                        fontFamily: theme.mono,
                        fontSize: 24,
                        color: f.c,
                        width: 110,
                      }}
                    >
                      {f.k}
                    </div>
                    <div style={{ fontSize: 25, color: theme.textDim }}>
                      {f.v}
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 30 }}>
              <Lines
                delay={160}
                fontSize={26}
                items={[
                  <>
                    A command becomes a <Mono>proposal</Mono>, never a direct
                    mutation
                  </>,
                  <>Sections are also editable by hand, in the reader or LaTeX view</>,
                ]}
              />
            </div>
          </div>
          <div style={{ flex: 1, position: "relative" }}>
            <Shot
              src="shots/09_edit_diff_integrity.png"
              width={980}
              delay={40}
              zoom={1.06}
            />
          </div>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

export const EditDiff: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "70px 90px" }}>
      <SceneHeader
        step="Step 4 · Approve"
        title="Word-level diffs you approve one by one"
      />
      <div style={{ display: "flex", gap: 48, marginTop: 32, alignItems: "flex-start" }}>
        <div style={{ width: 1160 }}>
          <Shot
            src="shots/09_edit_diff_integrity.png"
            width={1160}
            delay={10}
            zoom={1}
           />
        </div>
        <div style={{ flex: 1, marginTop: 26 }}>
          <Card title="Every proposal ships with" delay={26}>
            <Lines
              delay={34}
              fontSize={25}
              items={[
                <>Per-section diffs, additions in green, removals struck out</>,
                <>New references with the source they came from</>,
                <>
                  A citation-count check per section —{" "}
                  <Mono>13 → 13</Mono>
                </>,
              ]}
            />
          </Card>
          <div style={{ marginTop: 24, display: "flex", flexWrap: "wrap", gap: 12 }}>
            <Chip delay={90} size={23} color={theme.green}>
              approve per change
            </Chip>
            <Chip delay={98} size={23} color={theme.red}>
              reject all
            </Chip>
            <Chip delay={106} size={23} color={theme.amber}>
              violating changes can’t be applied
            </Chip>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  </SceneShell>
);

export const Export: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const files = [
    { f: "main.tex", d: "natbib/cite commands, bibliography rendered by citeproc" },
    { f: "references.bib", d: "canonical CSL-JSON → BibTeX" },
    { f: "paper.md", d: "readable Markdown" },
    { f: "paper.json", d: "the full canonical model" },
    { f: "PROVENANCE.md", d: "every agent-added source, plus edit history" },
  ];
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: "70px 90px", display: "flex", gap: 52 }}>
        <div style={{ width: 720, flexShrink: 0 }}>
          <SceneHeader
            step="Step 5 · Export"
            title="A LaTeX project, not a text dump"
            subtitle="Pick any vendored CSL style — the detected one is preselected."
          />
          <div
            style={{
              marginTop: 34,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            {files.map((f, i) => {
              const s = spring({
                frame: frame - 30 - i * 16,
                fps,
                config: { damping: 200 },
              });
              return (
                <div
                  key={f.f}
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 18,
                    opacity: s,
                    transform: `translateX(${interpolate(s, [0, 1], [-16, 0])}px)`,
                  }}
                >
                  <div
                    style={{
                      fontFamily: theme.mono,
                      fontSize: 27,
                      color: theme.green,
                      minWidth: 260,
                    }}
                  >
                    {f.f}
                  </div>
                  <div style={{ fontSize: 24, color: theme.textDim }}>{f.d}</div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 34 }}>
            <Chip delay={130} color={theme.purple}>
              provenance travels with the paper
            </Chip>
          </div>
        </div>
        <div style={{ flex: 1, position: "relative", alignSelf: "center" }}>
          <Shot
            src="shots/11_export.png"
            width={1020}
            delay={14}
            zoom={1.05}
          />
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};
