/** The app's Perk design system, lifted from frontend/src/styles.css so the
 *  video looks like the product rather than a deck about it.
 *
 *  Electric lime on warm parchment. Layers separate by tone, not shadow:
 *  white canvas → parchment → lime accent → dark charcoal island. Two weights
 *  only, 400 and 500 — the app never bolds anything. */
export const theme = {
  // surfaces
  bg: "#ffffff",              // surface 0 — page canvas
  bgSoft: "#f5f5eb",          // surface 1 — parchment
  panel: "#ffffff",           // cards lift by tone alone
  island: "#30302a",          // surface 3 — the dark inset (LaTeX, logs)
  islandLine: "#3d3d35",
  islandText: "#f5f5eb",

  // ink
  text: "#14140f",
  textDim: "#6e6e64",
  textFaint: "#919183",
  line: "#d2d2c8",
  lineStrong: "#919183",

  // the single chromatic voice
  accent: "#beff50",
  accentInk: "#14140f",       // text ON lime
  accentSoft: "rgba(190, 255, 80, 0.34)",

  // status — warm ink-family tones, never filled surfaces
  good: "#4f7a12",
  warn: "#8a6410",
  bad: "#9c3b2e",

  // aliases kept so scene code written against the old dark palette keeps
  // compiling; they now point at Perk values.
  panelLine: "#d2d2c8",
  green: "#4f7a12",
  amber: "#8a6410",
  red: "#9c3b2e",
  purple: "#6e6e64",

  radiusCard: 28,
  radiusInner: 18,
  radiusPill: 9999,

  mono: "'SF Mono','JetBrains Mono','Menlo','Consolas',monospace",
  sans: "'Geist','Inter','SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif",
  serif: "'Source Serif 4','Source Serif Pro','Iowan Old Style','Georgia',serif",
} as const;

export const FPS = 30;

/** Frames of cross-fade between scenes. */
export const OVERLAP = 8;

/** Breathing room after a line of narration ends, so a scene doesn't cut
 *  the instant the voice stops. */
export const TAIL_SECONDS = 0.9;
