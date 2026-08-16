/* Typographic-weight stroke icons. Single source, currentColor, 1.6 stroke —
   Perk treats icons as glyphs, not illustrations. */
type P = { size?: number };
const s = (n = 16) => ({
  width: n, height: n, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.6,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
});

export const Icon = {
  overview: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M3 11l9-8 9 8" /><path d="M5 9.5V20h14V9.5" /></svg>
  ),
  paper: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" /><path d="M9 13h6M9 17h4" /></svg>
  ),
  download: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4" />
      <path d="M8 11l4 4 4-4" /><path d="M12 15V3" /></svg>
  ),
  doc: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" /></svg>
  ),
  plus: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M12 5v14M5 12h14" /></svg>
  ),
  pages: ({ size }: P = {}) => (
    <svg {...s(size)}><rect x="4" y="3" width="12" height="16" rx="2" />
      <path d="M8 21h10a2 2 0 0 0 2-2V8" /></svg>
  ),
  sections: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M4 6h16M4 11h10M4 16h16M4 21h7" /></svg>
  ),
  quote: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M9 7H5a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v3H4" />
      <path d="M20 7h-4a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v3h-3" /></svg>
  ),
  link: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1" />
      <path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1" /></svg>
  ),
  unlink: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M9 15l-2 2a4 4 0 0 1-5.7-5.7l2-2" />
      <path d="M15 9l2-2a4 4 0 0 1 5.7 5.7l-2 2" /><path d="M4 4l16 16" /></svg>
  ),
  image: ({ size }: P = {}) => (
    <svg {...s(size)}><rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.5" /><path d="M21 16l-5-5L6 20" /></svg>
  ),
  search: ({ size }: P = {}) => (
    <svg {...s(size)}><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
  ),
  spark: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" />
      <path d="M18.5 16.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" /></svg>
  ),
  check: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M4 12.5l5 5L20 6.5" /></svg>
  ),
  alert: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17.2v.1" /></svg>
  ),
  pencil: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M4 20h4L20 8a2.8 2.8 0 0 0-4-4L4 16z" /><path d="M14.5 5.5l4 4" /></svg>
  ),
  arrow: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
  ),
  external: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M14 4h6v6" /><path d="M20 4l-9 9" />
      <path d="M18 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" /></svg>
  ),
  upload: ({ size }: P = {}) => (
    <svg {...s(size)}><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4" />
      <path d="M8 8l4-4 4 4" /><path d="M12 4v12" /></svg>
  ),
};

/** Upload-state illustration: a page with a lime spark settling onto it. */
export function DropIllustration({ active }: { active?: boolean }) {
  return (
    <svg className={`drop-art ${active ? "on" : ""}`} width="132" height="104"
      viewBox="0 0 132 104" fill="none" aria-hidden="true">
      <rect className="da-sheet" x="34" y="14" width="64" height="80" rx="8"
        fill="var(--color-pure-white)" stroke="var(--ink)" strokeWidth="1.6" />
      <path className="da-line" d="M46 36h40M46 46h40M46 56h28" stroke="var(--color-ash)"
        strokeWidth="2.6" strokeLinecap="round" />
      <path className="da-line da-line-lime" d="M46 66h22" stroke="var(--accent)"
        strokeWidth="2.6" strokeLinecap="round" />
      <g className="da-spark">
        <path d="M100 30l2.6 7.4L110 40l-7.4 2.6L100 50l-2.6-7.4L90 40l7.4-2.6z"
          fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.4" strokeLinejoin="round" />
      </g>
      <circle className="da-dot da-dot-1" cx="22" cy="30" r="3" fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.2" />
      <circle className="da-dot da-dot-2" cx="112" cy="72" r="2.4" fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.2" />
      <circle className="da-dot da-dot-3" cx="18" cy="76" r="2" fill="none" stroke="var(--ink)" strokeWidth="1.2" />
    </svg>
  );
}

/** Empty-state glyph for panels with nothing in them yet. */
export function EmptyArt({ kind }: { kind: "review" | "edit" }) {
  return (
    <svg className="empty-art" width="88" height="64" viewBox="0 0 88 64" fill="none" aria-hidden="true">
      <rect x="14" y="8" width="44" height="48" rx="6"
        fill="var(--color-pure-white)" stroke="var(--ink)" strokeWidth="1.6" />
      <path d="M24 24h24M24 32h24M24 40h14" stroke="var(--color-ash)" strokeWidth="2.4" strokeLinecap="round" />
      {kind === "review" ? (
        <g className="ea-float">
          <circle cx="64" cy="40" r="12" fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.6" />
          <circle cx="64" cy="40" r="5" fill="none" stroke="var(--ink)" strokeWidth="1.6" />
          <path d="M68 44l5 5" stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round" />
        </g>
      ) : (
        <g className="ea-float">
          <path d="M56 46l5 0 13-13a3.5 3.5 0 0 0-5-5L56 41z"
            fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.6" strokeLinejoin="round" />
        </g>
      )}
    </svg>
  );
}
