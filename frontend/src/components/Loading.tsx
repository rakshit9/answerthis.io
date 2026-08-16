/** Centred wait state for work that rebuilds a document.
 *
 *  The bars stand in for lines of the thing being assembled and fill in
 *  sequence, so the animation says "a document is being laid out" rather
 *  than the generic "something is happening" of a spinner. It is honest
 *  about being indeterminate — nothing here claims to track real progress.
 *  Where the backend *does* report real stages, use ParsingView instead.
 *
 *  `tone="dark"` is for the LaTeX island, which sits on charcoal. */

export function Loading({ label, tone = "light" }: {
  label: string;
  tone?: "light" | "dark";
}) {
  return (
    <div className={`loading loading-${tone}`} role="status" aria-live="polite">
      <div className="loading-doc" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => <i key={i} style={{ animationDelay: `${i * 0.14}s` }} />)}
      </div>
      <div className="loading-label">{label}</div>
    </div>
  );
}
