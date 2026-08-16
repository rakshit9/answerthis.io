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

/** A screenshot in a faux browser window, with an optional slow pan/zoom. */
export const Shot: React.FC<{
  src: string;
  width: number;
  delay?: number;
  zoom?: number;
  focus?: { x: number; y: number };
  label?: string;
  /** Callouts, positioned in percentages of the image area. */
  children?: React.ReactNode;
}> = ({ src, width, delay = 0, zoom = 1.06, focus, label, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 200, mass: 0.9 },
  });
  const scale = interpolate(frame - delay, [0, 260], [1, zoom], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const height = (width / 1440) * 900;
  const originX = focus ? `${focus.x * 100}%` : "50%";
  const originY = focus ? `${focus.y * 100}%` : "40%";
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
      <div style={{ height, overflow: "hidden", position: "relative" }}>
        <Img
          src={staticFile(src)}
          style={{
            width: "100%",
            display: "block",
            transform: `scale(${scale})`,
            transformOrigin: `${originX} ${originY}`,
          }}
        />
      </div>
      </div>
      {/* Callout layer: same box as the image, but free to overflow. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 34,
          width: "100%",
          height,
        }}
      >
        {children}
      </div>
    </div>
  );
};

/** Highlight rectangle drawn over a Shot, in Shot-relative percentages. */
export const Callout: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  text: string;
  delay?: number;
  color?: string;
  /** Where the label sits relative to the box. */
  place?: "left" | "right" | "top" | "bottom";
}> = ({ x, y, w, h, text, delay = 0, color = theme.accent, place = "right" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 200 } });

  const labelPos: React.CSSProperties =
    place === "right"
      ? { top: "50%", left: "calc(100% + 16px)", transform: "translateY(-50%)" }
      : place === "left"
        ? { top: "50%", right: "calc(100% + 16px)", transform: "translateY(-50%)" }
        : place === "top"
          ? { bottom: "calc(100% + 12px)", left: 0 }
          : { top: "calc(100% + 12px)", left: 0 };

  return (
    <div
      style={{
        position: "absolute",
        left: `${x}%`,
        top: `${y}%`,
        width: `${w}%`,
        height: `${h}%`,
        border: `2px solid ${color}`,
        borderRadius: 8,
        background: `${color}14`,
        opacity: s,
        transform: `scale(${interpolate(s, [0, 1], [0.96, 1])})`,
      }}
    >
      <div
        style={{
          position: "absolute",
          whiteSpace: "nowrap",
          fontFamily: theme.mono,
          fontSize: 22,
          // Ink on a filled lime pill, the way the app labels anything —
          // lime text on parchment is unreadable, and it has to stay legible
          // sitting on top of a screenshot.
          color: theme.accentInk,
          background: color,
          borderRadius: theme.radiusPill,
          padding: "8px 16px",
          ...labelPos,
        }}
      >
        {text}
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
