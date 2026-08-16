/**
 * Scenes for the parts of the product the first cut of this video predated:
 * the honesty guarantees, the citation styles the parser covers, citations as
 * links, accepting a review finding, surfaced API failures, and the editable
 * LaTeX view.
 *
 * All of them lean on the shared Shot and Card components so they sit in the
 * same visual language as the rest of the tour.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Card, SceneHeader, SceneShell, Shot } from "../components";
import { theme } from "../theme";

/** A row that slides in from the left, staggered by index. */
const Row: React.FC<{ i: number; children: React.ReactNode; delay?: number }> = ({
  i, children, delay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay - i * 9, fps, config: { damping: 200 } });
  return (
    <div style={{ opacity: s, transform: `translateX(${interpolate(s, [0, 1], [-26, 0])}px)` }}>
      {children}
    </div>
  );
};

const Pill: React.FC<{ children: React.ReactNode; tone?: "ink" | "lime" | "warn" }> = ({
  children, tone = "ink",
}) => (
  <span
    style={{
      display: "inline-block",
      padding: "8px 18px",
      borderRadius: theme.radiusPill,
      fontSize: 26,
      fontFamily: theme.mono,
      background: tone === "lime" ? theme.accent : "transparent",
      color: tone === "warn" ? theme.warn : theme.text,
      border: tone === "lime" ? "none" : `1px solid ${theme.line}`,
    }}
  >
    {children}
  </span>
);

// ------------------------------------------------------------------ honesty
export const Honesty: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "110px 120px" }}>
      <SceneHeader
        step="Non-negotiable"
        title="It says what it could not do"
        subtitle="Nothing is silently dropped — every failure is surfaced with a reason."
      />
      <div style={{ marginTop: 64, display: "flex", flexDirection: "column", gap: 22 }}>
        {[
          ["39 in-text markers could not be linked", "left in the text, reported — never deleted"],
          ["0 of 152 references unparsed", "low-confidence entries keep their raw text"],
          ["This PDF has no extractable text layer", "a scan is refused, not parsed into an empty document"],
          ["openalex search failed — quota exhausted", "a dead API never looks like “nothing found”"],
        ].map(([head, sub], i) => (
          <Row key={head} i={i} delay={22}>
            <Card style={{ padding: "26px 32px", display: "flex", gap: 26, alignItems: "baseline" }}>
              <span style={{ color: theme.warn, fontSize: 30, fontFamily: theme.mono }}>!</span>
              <span>
                <div style={{ fontSize: 32, fontWeight: 500 }}>{head}</div>
                <div style={{ fontSize: 25, color: theme.textDim, marginTop: 6 }}>{sub}</div>
              </span>
            </Card>
          </Row>
        ))}
      </div>
    </AbsoluteFill>
  </SceneShell>
);

// ------------------------------------------------------------------- styles
export const Styles: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ padding: "110px 120px" }}>
        <SceneHeader
          step="Stage E"
          title="Four citation families, detected"
          subtitle="Style detection is scored and shown with its confidence — and you can override it."
        />
        <div style={{ marginTop: 70, display: "flex", flexWrap: "wrap", gap: 20, maxWidth: 1500 }}>
          {[
            "[12]", "[1, 3–5]", "word¹²", "(1)", "(1, 3)",
            "(Smith et al., 2020)", "Vaswani et al. (2017)", "[Smith et al. 2020]",
          ].map((s, i) => (
            <Row key={s} i={i} delay={20}>
              <Pill tone={i === 7 ? "lime" : "ink"}>{s}</Pill>
            </Row>
          ))}
        </div>
        <Row i={0} delay={110}>
          <Card style={{ marginTop: 56, padding: "30px 36px", maxWidth: 1360 }}>
            <div style={{ fontSize: 30, fontWeight: 500 }}>
              Müller · Álvarez · Öztürk
            </div>
            <div style={{ fontSize: 25, color: theme.textDim, marginTop: 10, lineHeight: 1.5 }}>
              Python's <span style={{ fontFamily: theme.mono }}>[A-Z]</span> is ASCII-only, so
              these matched nothing and collapsed a whole reference list into one block.
              Surname matching is Unicode-aware.
            </div>
          </Card>
        </Row>
        {/* the guard that stops equation numbers becoming citations */}
        <div
          style={{
            marginTop: 40,
            fontSize: 25,
            color: theme.textDim,
            opacity: interpolate(frame, [140, 165], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }),
          }}
        >
          “(3)” is also how a paper references equation 3 — so parenthesised numerics need
          three linked markers and no bracket style before they are trusted.
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

// ----------------------------------------------------------- citation click
export const CitationClick: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "96px 120px" }}>
      <SceneHeader step="Reader" title="Every citation is a link" />
      <div style={{ marginTop: 44, display: "flex", justifyContent: "center" }}>
        <Shot src="shots/05_citation_to_reference.png" width={1230} delay={10} label="localhost:8000" />
      </div>
    </AbsoluteFill>
  </SceneShell>
);

// --------------------------------------------------------------- cite this
export const CiteThis: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "96px 120px" }}>
      <SceneHeader
        step="Review → edit"
        title="Accept a finding as a citation"
        subtitle="Cites that exact source, at that exact sentence — you still approve it."
      />
      <div style={{ marginTop: 44, display: "flex", justifyContent: "center" }}>
        <Shot src="shots/08_missing_work_cite.png" width={1100} delay={10} label="localhost:8000" />
      </div>
    </AbsoluteFill>
  </SceneShell>
);

// ---------------------------------------------------------------- failures
export const Failures: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 24, fps, config: { damping: 200 } });
  return (
    <SceneShell durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 160px" }}>
        <SceneHeader title="A failed search says so" />
        <div
          style={{
            marginTop: 52,
            width: "100%",
            maxWidth: 1400,
            background: theme.island,
            color: theme.islandText,
            borderRadius: theme.radiusInner,
            padding: "38px 44px",
            fontFamily: theme.mono,
            fontSize: 27,
            lineHeight: 1.75,
            opacity: s,
            transform: `translateY(${interpolate(s, [0, 1], [22, 0])}px)`,
          }}
        >
          <div style={{ color: "#b9b9b7" }}>[00:48:45] openalex search “operational definitions…”</div>
          <div style={{ color: theme.accent }}>  FAILED · quota exhausted (HTTP 429)</div>
          <div style={{ color: "#b9b9b7" }}>[00:48:45] semantic_scholar search “operational definitions…”</div>
          <div style={{ color: "#b9b9b7" }}>  → 8 results</div>
        </div>
        <div style={{ marginTop: 34, fontSize: 29, color: theme.textDim, textAlign: "center", maxWidth: 1200 }}>
          Surfaced as its own finding — so a rate-limited API can never be mistaken
          for an honest empty result.
        </div>
      </AbsoluteFill>
    </SceneShell>
  );
};

// ------------------------------------------------------------------- latex
export const LatexEdit: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => (
  <SceneShell durationInFrames={durationInFrames}>
    <AbsoluteFill style={{ padding: "96px 120px" }}>
      <SceneHeader
        step="LaTeX"
        title="The source is editable too"
        subtitle="Regenerated live from the canonical model — type in it, and the reader updates."
      />
      <div style={{ marginTop: 44, display: "flex", justifyContent: "center" }}>
        <Shot src="shots/10_latex_editable.png" width={1100} delay={10} label="localhost:8000" />
      </div>
    </AbsoluteFill>
  </SceneShell>
);
