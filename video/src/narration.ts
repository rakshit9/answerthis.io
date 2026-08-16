/** Voice-over script. One entry per scene, keyed by scene id.
 *
 *  `scripts/voice.sh` renders these to public/vo/<id>.wav with macOS `say`,
 *  and writes public/vo/durations.json. Scene lengths are derived from those
 *  durations, so the picture always fits the words — change a line here, run
 *  the script, and the timing follows.
 */
export const NARRATION: Record<string, string> = {
  title:
    "Paper Improvement Agent. Upload a research paper, get a peer review grounded in real citations, and improve it without ever breaking one.",
  overview:
    "Four steps. Parse the PDF. Review it against real academic search. Edit it by natural language. Export it as LaTeX.",
  upload:
    "The first screen is the product. Drop a PDF — arXiv papers work best, because their references resolve.",
  pipeline:
    "Parsing is six documented stages, and the app narrates its own pipeline as it runs. Extract text and layout. Capture floats. Build the structure. Segment the reference list. Parse each entry into fields. Link the in-text citations.",
  parseResult:
    "On a real twenty-four page paper: seventeen sections, one hundred fifty-two references, one hundred thirty-three citation markers linked, and two floats lifted out of the prose.",
  honesty:
    "What it cannot parse, it says so. Unlinked markers are surfaced rather than dropped, and a scanned PDF with no text layer is refused with a reason instead of parsing into an empty document.",
  styles:
    "Numeric brackets, superscripts, parenthesised numbers, and author–year — including bracketed forms, and non-ASCII surnames like Müller and Álvarez that a naive parser silently misses.",
  resolve:
    "Every reference is matched against OpenAlex and Semantic Scholar, down a ladder of DOI, then arXiv, then title — with per-reference status you can inspect.",
  reader:
    "The paper renders through citeproc in the detected style. A structure rail moves between sections, and every citation is a link.",
  citationClick:
    "Click a citation and it jumps to the work it cites and flashes the entry. One click takes you back to where you were reading.",
  reviewRun:
    "Peer review runs on request, never automatically, and you choose what it checks.",
  missingWork:
    "Missing work: papers you plausibly should cite, found by real search across both APIs and deduped against your bibliography. Every one is a real, linkable source.",
  citeThis:
    "Accept one, and it proposes citing that exact source at that exact sentence — through the same approval path as any other edit.",
  claimChecks:
    "Claim–citation checks fetch the cited work's abstract and judge whether it actually supports your sentence, with a verbatim quote that is verified against the real abstract before you ever see it.",
  failures:
    "When a search fails, it says so. A dead API never looks like nothing found.",
  editCommand:
    "Edit by command. The agent plans typed operations instead of running one giant prompt, and logs every step it takes.",
  editDiff:
    "Every change arrives as a proposal: an inline diff in the manuscript, new sources with their provenance, and a citation-integrity verdict. You approve each change yourself.",
  tokens:
    "Citations live as tokens inside the text, so prose can move without losing what it cites. Edits that would break a citation are unapplyable by construction.",
  latex:
    "The LaTeX view is the same document regenerated live — and it is editable. Type into main dot tex and the reader updates. It works in both directions.",
  export:
    "Export a LaTeX project: main dot tex, references dot bib, the full canonical model, and a provenance file naming where every added citation came from.",
  architecture:
    "CSL-JSON is the single canonical citation model, rendered by citeproc with real style files. One hundred and sixteen tests cover the core behaviour, with no live network calls.",
  runIt:
    "Run the whole thing with one command. Docker compose up.",
  outro:
    "Paper Improvement Agent. Grounded in real sources — and honest when it cannot be.",
};

export const SCENE_ORDER = [
  "title", "overview", "upload", "pipeline", "parseResult", "honesty",
  "styles", "resolve", "reader", "citationClick", "reviewRun", "missingWork",
  "citeThis", "claimChecks", "failures", "editCommand", "editDiff", "tokens",
  "latex", "export", "architecture", "runIt", "outro",
] as const;

export type SceneId = (typeof SCENE_ORDER)[number];
