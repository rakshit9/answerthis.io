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

const Split: React.FC<{
  left: React.ReactNode;
  right: React.ReactNode;
  leftWidth?: number;
}> = ({ left, right, leftWidth = 620 }) => (
  <AbsoluteFill
    style={{
      padding: "92px 90px",
      display: "flex",
      flexDirection: "row",
      alignItems: "center",
      gap: 64,
    }}
  >
    <div style={{ width: leftWidth, flexShrink: 0 }}>{left}</div>
    <div style={{ flex: 1, position: "relative" }}>{right}</div>
  </AbsoluteFill>
);

export const Upload: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <Split
      left={
        <>
          <SceneHeader
            step="Step 1 · Upload"
            title="Drop a PDF"
            subtitle="No account, no setup. The file goes straight into the parsing pipeline."
          />
          <div style={{ marginTop: 40 }}>
            <Lines
              delay={26}
              items={[
                <>
                  arXiv papers resolve best on both APIs
                </>,
                <>
                  A scanned, image-only PDF is <Mono color={theme.red}>refused with a reason</Mono>{" "}
                  instead of parsing to an empty document
                </>,
                <>
                  State persists on disk — reopen the paper later from the
                  papers list
                </>,
              ]}
            />
          </div>
        </>
      }
      right={
        <div style={{ position: "relative" }}>
          <Shot src="shots/01_upload.png" width={1080} delay={12} zoom={1.04} />
        </div>
      }
    />
  </SceneShell>
);

const STAGES = [
  { id: "A", name: "pdf_extract", detail: "text lines, body font size, two-column detection per page" },
  { id: "A′", name: "floats", detail: "figures, tables and boxed panels lifted out of the prose flow" },
  { id: "B", name: "structure", detail: "title, abstract, nested section tree" },
  { id: "C", name: "reflist", detail: "reference-list segmentation — numbered / author-year strategies" },
  { id: "D", name: "refparse", detail: "entries → structured CSL-JSON fields, unparsed ones kept and flagged" },
  { id: "E", name: "intext", detail: "in-text marker groups linked to references, style + confidence" },
];

export const Pipeline: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const per = 32;
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: "92px 100px" }}>
        <SceneHeader
          step="Step 1 · Parse"
          title="A deterministic pipeline — no LLM"
          subtitle="The parse view narrates its own stages while they run, so you can see where a paper broke instead of guessing."
        />
        <div
          style={{
            marginTop: 56,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {STAGES.map((st, i) => {
            const start = 24 + i * per;
            const s = spring({
              frame: frame - start,
              fps,
              config: { damping: 200 },
            });
            const done = frame > start + per * 0.8;
            return (
              <div
                key={st.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  padding: "18px 26px",
                  borderRadius: 14,
                  border: `1px solid ${done ? theme.green + "55" : theme.panelLine}`,
                  background: done ? `${theme.green}0f` : theme.panel,
                  opacity: s,
                  transform: `translateX(${interpolate(s, [0, 1], [-24, 0])}px)`,
                }}
              >
                <div
                  style={{
                    width: 54,
                    fontFamily: theme.mono,
                    fontSize: 32,
                    fontWeight: 500,
                    color: theme.good,   /* lime is a surface, not text — use the deep lime ink */
                  }}
                >
                  {st.id}
                </div>
                <div
                  style={{
                    width: 240,
                    fontFamily: theme.mono,
                    fontSize: 30,
                    color: theme.text,
                  }}
                >
                  {st.name}
                </div>
                <div style={{ flex: 1, fontSize: 26, color: theme.textDim }}>
                  {st.detail}
                </div>
                <div
                  style={{
                    fontFamily: theme.mono,
                    fontSize: 26,
                    color: done ? theme.green : theme.textFaint,
                  }}
                >
                  {done ? "ok" : "…"}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 44, display: "flex", gap: 14 }}>
          <Chip delay={228} color={theme.green}>
            same input → same output, every time
          </Chip>
          <Chip delay={238} color={theme.amber}>
            failures are surfaced, never swallowed
          </Chip>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

export const ParseResult: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "70px 90px" }}>
      <SceneHeader
        step="Step 1 · Result"
        title="Everything the parser decided, on one screen"
      />
      <div
        style={{
          marginTop: 34,
          display: "flex",
          gap: 48,
          alignItems: "flex-start",
        }}
      >
        <div style={{ width: 1120 }}>
          <Shot
            src="shots/02_parse_live.png"
            width={1120}
            delay={10}
            zoom={1}
           />
        </div>
        <div style={{ flex: 1, marginTop: 40 }}>
          <Lines
            delay={30}
            fontSize={28}
            items={[
              <>
                Detected in-text style with a <Mono>confidence</Mono> score →
                mapped to a CSL style
              </>,
              <>Full section tree with per-section character counts</>,
              <>
                Unparseable reference entries are{" "}
                <Mono color={theme.amber}>kept and surfaced</Mono>, never dropped
              </>,
              <>Dropped rotated / header-footer lines are reported too</>,
            ]}
          />
        </div>
      </div>
    </AbsoluteFill>
  </SceneShell>
);

export const Resolve: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ladder = [
    { k: "DOI", v: "exact record lookup", c: theme.green },
    { k: "arXiv id", v: "exact record lookup", c: theme.accent },
    { k: "title", v: "fuzzy match, scored", c: theme.amber },
  ];
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <Split
        leftWidth={680}
        left={
          <>
            <SceneHeader
              step="Step 1 · Resolve"
              title="Matched against real records"
              subtitle="Every reference is resolved against OpenAlex and Semantic Scholar through a fallback ladder."
            />
            <div
              style={{
                marginTop: 40,
                display: "flex",
                flexDirection: "column",
                gap: 14,
              }}
            >
              {ladder.map((l, i) => {
                const s = spring({
                  frame: frame - 34 - i * 20,
                  fps,
                  config: { damping: 200 },
                });
                return (
                  <div
                    key={l.k}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 18,
                      opacity: s,
                      transform: `translateY(${interpolate(s, [0, 1], [16, 0])}px)`,
                    }}
                  >
                    <div
                      style={{
                        fontFamily: theme.mono,
                        fontSize: 30,
                        color: l.c,
                        border: `1px solid ${l.c}55`,
                        background: `${l.c}12`,
                        borderRadius: 10,
                        padding: "10px 18px",
                        minWidth: 170,
                        textAlign: "center",
                      }}
                    >
                      {l.k}
                    </div>
                    <div style={{ color: theme.textFaint, fontSize: 28 }}>→</div>
                    <div style={{ fontSize: 27, color: theme.textDim }}>
                      {l.v}
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 38 }}>
              <Lines
                delay={100}
                fontSize={26}
                items={[
                  <>Responses are disk-cached; retries back off on 429/5xx</>,
                  <>
                    Quota-exhausted responses fail fast and are{" "}
                    <Mono color={theme.amber}>reported, not retried</Mono>
                  </>,
                ]}
              />
            </div>
          </>
        }
        right={
          <div style={{ position: "relative" }}>
            <Shot
              src="shots/03_parse_overview.png"
              width={1020}
              delay={12}
              zoom={1.08}
              focus={{ x: 0.5, y: 0.8 }}
            />
          </div>
        }
      />
    </SceneShell>
  );
};

export const Reader: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => (
  <SceneShell durationInFrames={durationInFrames}>
    <Split
      leftWidth={640}
      left={
        <>
          <SceneHeader
            step="Step 2 · Read"
            title="The paper, rendered properly"
            subtitle="Labels and bibliography come out of citeproc using real vendored .csl styles — not string formatting."
          />
          <div style={{ marginTop: 36, display: "flex", flexWrap: "wrap", gap: 12 }}>
            <Chip delay={40} size={24}>APA</Chip>
            <Chip delay={46} size={24}>IEEE</Chip>
            <Chip delay={52} size={24}>Chicago</Chip>
            <Chip delay={58} size={24}>Harvard</Chip>
            <Chip delay={64} size={24}>Nature</Chip>
          </div>
          <div style={{ marginTop: 34 }}>
            <Lines
              delay={72}
              fontSize={27}
              items={[
                <>Click any citation to jump to its bibliography entry</>,
                <>A structure rail moves between sections</>,
                <>Style is auto-detected from the PDF, changeable on export</>,
              ]}
            />
          </div>
        </>
      }
      right={
        <div style={{ position: "relative" }}>
          <Shot src="shots/04_reader_citations.png" width={1060} delay={12} zoom={1.07} />
          <div
            style={{
              position: "absolute",
              bottom: -34,
              left: 0,
              fontFamily: theme.mono,
              fontSize: 24,
              color: theme.textFaint,
            }}
          >
            <Typewriter
              delay={90}
              cps={22}
              text="[[citep:ref_12]] → “[12]” → bibliography entry"
              style={{ color: theme.green, fontSize: 24 }}
            />
          </div>
        </div>
      }
    />
  </SceneShell>
);

export const Tokens: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 40, fps, config: { damping: 200 } });
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: "92px 100px", justifyContent: "center" }}>
        <SceneHeader
          step="Under the hood"
          title="Citations are tokens, not offsets"
          subtitle="The one decision the whole system rests on."
        />
        <div style={{ display: "flex", gap: 34, marginTop: 54 }}>
          <Card title="Section text as stored" delay={26} style={{ flex: 1 }}>
            <div
              style={{
                fontFamily: theme.mono,
                fontSize: 26,
                lineHeight: 1.7,
                color: theme.textDim,
              }}
            >
              Attention mechanisms are now vital{" "}
              <span style={{ color: theme.green }}>[[citep:ref_2]]</span>{" "}
              <span style={{ color: theme.green }}>[[citep:ref_19]]</span>, and
              we build on{" "}
              <span style={{ color: theme.green }}>[[citep:ref_27]]</span>.
            </div>
          </Card>
          <div
            style={{
              alignSelf: "center",
              fontSize: 44,
              color: theme.good,   /* lime is a surface, not text — use the deep lime ink */
              opacity: s,
            }}
          >
            →
          </div>
          <Card
            title="Why it matters"
            delay={40}
            accent={theme.green}
            style={{ flex: 1 }}
          >
            <Lines
              delay={48}
              fontSize={26}
              color={theme.textDim}
              items={[
                <>Tokens survive an LLM round-trip; character offsets do not</>,
                <>
                  Integrity checking becomes a{" "}
                  <Mono>multiset comparison</Mono> — before vs after
                </>,
                <>One token maps to one canonical CSL-JSON reference</>,
              ]}
            />
          </Card>
        </div>
        <div
          style={{
            marginTop: 46,
            display: "flex",
            gap: 14,
            justifyContent: "center",
          }}
        >
          <Chip delay={110} color={theme.red}>
            drop a citation → violation
          </Chip>
          <Chip delay={118} color={theme.red}>
            invent a citation → violation
          </Chip>
          <Chip delay={126} color={theme.green}>
            violations are unapplyable by construction
          </Chip>
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};
