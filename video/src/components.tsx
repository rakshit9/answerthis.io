import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { theme } from "./theme";

/** Fades a scene in at its start and out at its end. */
export const SceneShell: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
  background?: string;
}> = ({ durationInFrames, children, background }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, 12, durationInFrames - 12, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return (
    <AbsoluteFill
      style={{
        // Parchment, like the app's page canvas — cards lift to white on top.
        backgroundColor: background ?? theme.bgSoft,
        color: theme.text,
        fontFamily: theme.sans,
        opacity,
      }}
    >
      <Grid />
      {children}
    </AbsoluteFill>
  );
};

/** Subtle blueprint grid + glow, gives every scene a common floor. */
export const Grid: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${theme.line}55 1px, transparent 1px), linear-gradient(90deg, ${theme.line}55 1px, transparent 1px)`,
          backgroundSize: "64px 64px",
          transform: `translateY(${(frame * 0.12) % 64}px)`,
          opacity: 0.5,
        }}
      />
      {/* A soft lime wash from the top, the way the app's landing page sits
          on parchment rather than on a glow. */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(1200px 700px at 50% -12%, ${theme.accent}55, transparent 68%)`,
        }}
      />
    </AbsoluteFill>
  );
};

/** Kicker + headline block used at the top of most scenes. */
export const SceneHeader: React.FC<{
  step?: string;
  title: string;
  subtitle?: string;
  delay?: number;
}> = ({ step, title, subtitle, delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 200 } });
  return (
    <div
      style={{
        opacity: s,
        transform: `translateY(${interpolate(s, [0, 1], [18, 0])}px)`,
      }}
    >
      {step ? (
        <div
          style={{
            fontFamily: theme.mono,
            fontSize: 22,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: theme.good,   /* lime is a surface, not text — use the deep lime ink */
            marginBottom: 14,
          }}
        >
          {step}
        </div>
      ) : null}
      <div style={{ fontSize: 66, fontWeight: 500, letterSpacing: -1.6 }}>
        {title}
      </div>
      {subtitle ? (
        <div
          style={{
            fontSize: 30,
            color: theme.textDim,
            marginTop: 14,
            lineHeight: 1.45,
            maxWidth: 1180,
          }}
        >
          {subtitle}
        </div>
      ) : null}
    </div>
  );
};

/** A screenshot in a faux browser window.
 *
 *  Deliberately no zoom or pan. Scaling the image inside a fixed frame
 *  cropped the product at the edges — the left dock and the right panel
 *  were the first things to go — and the whole point of these shots is that
 *  the real UI is visible. The entrance is a fade and a small rise, which
 *  cannot cut anything off. */
export const Shot: React.FC<{
  src: string;
  width: number;
  delay?: number;
  label?: string;
}> = ({ src, width, delay = 0, label }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 200, mass: 0.9 },
  });
  // The screenshots are 1600×1000 (and 1440×900 before them) — both 1.6:1.
  const height = width / 1.6;
  return (
    <div
      style={{
        width,
        position: "relative",
        opacity: s,
        transform: `translateY(${interpolate(s, [0, 1], [26, 0])}px)`,
      }}
    >
      <div
        style={{
          borderRadius: 14,
          overflow: "hidden",
          border: `1px solid ${theme.panelLine}`,
          background: theme.panel,
          // Perk separates layers by tone, not elevation — just enough lift
          // to read the window against parchment.
          boxShadow: "0 24px 60px rgba(20,20,15,0.10)",
        }}
      >
      <div
        style={{
          height: 34,
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "0 14px",
          borderBottom: `1px solid ${theme.panelLine}`,
          background: theme.bgSoft,
        }}
      >
        {[theme.red, theme.amber, theme.green].map((c) => (
          <div
            key={c}
            style={{
              width: 10,
              height: 10,
              borderRadius: 999,
              background: c,
              opacity: 0.75,
            }}
          />
        ))}
        <div
          style={{
            marginLeft: 12,
            fontFamily: theme.mono,
            fontSize: 14,
            color: theme.textFaint,
          }}
        >
          {label ?? "localhost:8000"}
        </div>
      </div>
      <div style={{ height, position: "relative" }}>
        <Img
          src={staticFile(src)}
          style={{ width: "100%", height: "100%", display: "block", objectFit: "contain" }}
        />
      </div>
      </div>
    </div>
  );
};

export const Chip: React.FC<{
  children: React.ReactNode;
  color?: string;
  delay?: number;
  size?: number;
}> = ({ children, color = theme.accent, delay = 0, size = 26 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 200 } });
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        fontFamily: theme.mono,
        fontSize: size,
        color,
        border: `1px solid ${color}55`,
        background: `${color}14`,
        borderRadius: 999,
        padding: "10px 20px",
        opacity: s,
        transform: `translateY(${interpolate(s, [0, 1], [14, 0])}px)`,
      }}
    >
      {children}
    </div>
  );
};

export const Card: React.FC<{
  title?: string;
  children: React.ReactNode;
  delay?: number;
  accent?: string;
  style?: React.CSSProperties;
}> = ({ title, children, delay = 0, accent = theme.accent, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 200 } });
  return (
    <div
      style={{
        background: theme.panel,
        border: `1px solid ${theme.panelLine}`,
        borderRadius: 16,
        padding: 28,
        opacity: s,
        transform: `translateY(${interpolate(s, [0, 1], [22, 0])}px)`,
        ...style,
      }}
    >
      {title ? (
        <div
          style={{
            fontFamily: theme.mono,
            fontSize: 20,
            letterSpacing: 2,
            textTransform: "uppercase",
            color: accent,
            marginBottom: 16,
          }}
        >
          {title}
        </div>
      ) : null}
      {children}
    </div>
  );
};

/** Staggered list of lines. */
export const Lines: React.FC<{
  items: React.ReactNode[];
  delay?: number;
  stagger?: number;
  fontSize?: number;
  bullet?: string;
  color?: string;
}> = ({
  items,
  delay = 0,
  stagger = 8,
  fontSize = 30,
  bullet = "—",
  color = theme.textDim,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {items.map((item, i) => {
        const s = spring({
          frame: frame - delay - i * stagger,
          fps,
          config: { damping: 200 },
        });
        return (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 14,
              fontSize,
              color,
              lineHeight: 1.4,
              opacity: s,
              transform: `translateX(${interpolate(s, [0, 1], [-16, 0])}px)`,
            }}
          >
            <span style={{ color: theme.good }}>{bullet}</span>
            <span>{item}</span>
          </div>
        );
      })}
    </div>
  );
};

/** Character-by-character typewriter with a blinking caret. */
export const Typewriter: React.FC<{
  text: string;
  delay?: number;
  cps?: number;
  style?: React.CSSProperties;
  caret?: boolean;
}> = ({ text, delay = 0, cps = 26, style, caret = true }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const chars = Math.max(
    0,
    Math.floor(((frame - delay) / fps) * cps),
  );
  const shown = text.slice(0, chars);
  const done = chars >= text.length;
  const blink = Math.floor(frame / 15) % 2 === 0;
  return (
    <span style={{ fontFamily: theme.mono, ...style }}>
      {shown}
      {caret && (!done || blink) ? (
        <span style={{ color: theme.good }}>▌</span>
      ) : null}
    </span>
  );
};

export const Mono: React.FC<{
  children: React.ReactNode;
  color?: string;
}> = ({ children, color = theme.green }) => (
  <span style={{ fontFamily: theme.mono, color }}>{children}</span>
);
