import { useEffect, useState } from "react";

/** Structure rail for the reader, the counterpart of the LaTeX view's outline.
 *
 *  Both are driven by the same canonical sections, so the two views agree on
 *  what the paper's structure is. Each entry carries the section's parsed
 *  *kind* — abstract / body / references — because that classification is a
 *  parsing decision the user should be able to see and disagree with, not an
 *  invisible internal label.
 *
 *  The active entry is tracked by observing the sections themselves rather
 *  than by arithmetic on scroll offsets, so it stays correct when a section
 *  grows or shrinks mid-session (an applied edit does exactly that). */

export type OutlineSection = { id: string; title: string; level: number; kind: string };

/** SectionKind → rail label. "body" is the unremarkable default and would be
 *  noise on every row, so it stays unlabelled. */
const KIND_LABEL: Record<string, string> = {
  abstract: "abstract",
  references: "refs",
  other: "back",
};

export function ReaderOutline({ sections, onJump }: {
  sections: OutlineSection[];
  onJump: (sectionId: string) => void;
}) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (!sections.length) return;
    // Watch a band near the top of the pane: a section counts as "current"
    // once its heading reaches the top quarter and until the next one does.
    const seen = new Map<string, number>();
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          seen.set(e.target.id.replace("psec-", ""),
            e.isIntersecting ? e.intersectionRatio : 0);
        });
        const visible = sections.filter((s) => (seen.get(s.id) ?? 0) > 0);
        if (visible.length) setActive(visible[0].id);
      },
      { rootMargin: "-8% 0px -70% 0px", threshold: [0, 0.01] });

    const els = sections
      .map((s) => document.getElementById(`psec-${s.id}`))
      .filter((el): el is HTMLElement => el !== null);
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [sections]);

  if (sections.length < 2) return null;

  return (
    <nav className="reader-outline" aria-label="Paper structure">
      <div className="reader-outline-head">Structure</div>
      <div className="reader-outline-list">
        {sections.map((s) => (
          <button key={s.id}
            className={`ro-item lvl${Math.min(s.level, 3)} ${active === s.id ? "on" : ""}`}
            title={s.title}
            onClick={() => onJump(s.id)}>
            <span className="ro-title">{s.kind === "abstract" ? "Abstract" : s.title}</span>
            {KIND_LABEL[s.kind] && <span className="ro-kind">{KIND_LABEL[s.kind]}</span>}
          </button>
        ))}
      </div>
    </nav>
  );
}
