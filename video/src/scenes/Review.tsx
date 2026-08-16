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
} from "../components";
import { theme } from "../theme";

export const ReviewRun: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const steps = [
    "search OpenAlex + Semantic Scholar for missing work",
    "dedupe hits against your bibliography",
    "fetch cited abstracts for claim checks",
    "judge claim vs abstract, quote the evidence",
  ];
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill
        style={{ padding: "80px 90px", display: "flex", gap: 56 }}
      >
        <div style={{ width: 660, flexShrink: 0 }}>
          <SceneHeader
            step="Step 3 · Peer review"
            title="A review that shows its work"
            subtitle="It runs against the live APIs, and reports what it did — including what failed."
          />
          <div
            style={{
              marginTop: 40,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            {steps.map((t, i) => {
              const s = spring({
                frame: frame - 30 - i * 22,
                fps,
                config: { damping: 200 },
              });
              const done = frame > 30 + i * 22 + 26;
              return (
                <div
                  key={t}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    fontSize: 27,
                    color: theme.textDim,
                    opacity: s,
                    transform: `translateX(${interpolate(s, [0, 1], [-18, 0])}px)`,
                  }}
                >
                  <span
                    style={{
                      fontFamily: theme.mono,
                      color: done ? theme.green : theme.textFaint,
                      width: 34,
                    }}
                  >
                    {done ? "✓" : "•"}
                  </span>
                  {t}
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 36, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Chip delay={130} size={23} color={theme.amber}>
              max 10 searches / review
            </Chip>
            <Chip delay={138} size={23} color={theme.amber}>
              max 12 claim checks
            </Chip>
          </div>
        </div>
        <div style={{ flex: 1, position: "relative", alignSelf: "center" }}>
          <Shot
            src="shots/06_review_findings.png"
            width={1040}
            delay={12}
          />
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

export const MissingWork: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "70px 90px" }}>
      <SceneHeader
        step="Step 3 · Findings"
        title="Three kinds of finding — and honest failures"
        subtitle="This run hit OpenAlex’s daily budget, so it says exactly that on every reference it couldn’t resolve."
      />
      <div style={{ display: "flex", gap: 48, marginTop: 30 }}>
        <div style={{ width: 1080 }}>
          <Shot
            src="shots/08_missing_work_cite.png"
            width={1080}
            delay={10}
          />
        </div>
        <div style={{ flex: 1, marginTop: 10 }}>
          <Card title="Finding types" delay={26}>
            <Lines
              delay={34}
              fontSize={25}
              items={[
                <>
                  <Mono color={theme.accent}>missing work</Mono> — search across
                  both APIs, deduped against your bibliography
                </>,
                <>
                  <Mono color={theme.amber}>claim mismatch</Mono> — the citation
                  doesn’t support the sentence
                </>,
                <>
                  <Mono color={theme.red}>unresolved reference</Mono> — with the
                  exact API error (HTTP 429, budget exhausted)
                </>,
              ]}
            />
          </Card>
          <div style={{ marginTop: 24 }}>
            <Card title="Every finding carries" delay={70} accent={theme.green}>
              <Lines
                delay={78}
                fontSize={25}
                color={theme.textDim}
                items={[
                  <>
                    A linkable source and its <Mono>provenance</Mono> — which
                    API, which model
                  </>,
                  <>
                    <Mono color={theme.accent}>“Cite this”</Mono> proposes that
                    exact source at that exact sentence
                  </>,
                  <>
                    Failed searches are listed, so silence is never mistaken for
                    a clean bill
                  </>,
                ]}
              />
            </Card>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  </SceneShell>
);

export const ClaimChecks: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "70px 90px" }}>
      <SceneHeader
        step="Step 3 · Claim checks"
        title="Does the cited paper actually say that?"
        subtitle="It fetches the cited work’s abstract, judges support, and quotes the line — verified verbatim against the real abstract before it is shown."
      />
      <div style={{ display: "flex", gap: 48, marginTop: 30, alignItems: "flex-start" }}>
        <div style={{ width: 1120 }}>
          <Shot
            src="shots/07_claim_verdict.png"
            width={1120}
            delay={10}
           />
        </div>
        <div style={{ flex: 1, marginTop: 30 }}>
          <Lines
            delay={30}
            fontSize={27}
            items={[
              <>
                Verdicts: <Mono color={theme.green}>supports</Mono>,{" "}
                <Mono color={theme.amber}>partial</Mono>,{" "}
                <Mono color={theme.red}>mismatch</Mono>
              </>,
              <>No abstract available → it says so, rather than guessing</>,
              <>
                No LLM key configured → claim verdicts say they need one instead
                of faking output
              </>,
            ]}
          />
        </div>
      </div>
    </AbsoluteFill>
  </SceneShell>
);
