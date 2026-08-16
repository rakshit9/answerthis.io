# Feature tour video

A ~3.6 minute walkthrough of Paper Improvement Agent, built with
[Remotion](https://github.com/remotion-dev/remotion). Renders to
`out/paper-improvement-agent.mp4` (1920×1080, 30 fps, with voice-over).

```bash
cd video
npm install
npm run voice     # regenerate the narration (macOS `say`) + durations
npm run build     # copies ../screenshots in, then renders the mp4
npm run dev       # Remotion Studio, to scrub and edit interactively
```

`public/shots/` and `public/vo/*.wav` are generated, not committed — the
screenshots live once in [`../screenshots`](../screenshots) and the voice-over
is reproducible from the script. `npm run build` refreshes the shots for you,
so re-shooting the UI and re-rendering the video is two commands.

## How it is put together

**The script drives the timing.** [`src/narration.ts`](src/narration.ts) holds
one line per scene. `npm run voice` renders each to `public/vo/<id>.wav` and
writes the measured length to `public/vo/durations.json`; scene durations are
derived from those numbers plus a tail. Edit a line, rerun, and the picture
follows the words — no hand-tuned frame counts to keep in sync.

**Voice-over is macOS `say`** (offline, no key, nothing uploaded). It sounds
like what it is. To use a better TTS, drop WAVs with the same filenames into
`public/vo/` and rerun the durations step.

**The look is the product's.** [`src/theme.ts`](src/theme.ts) mirrors the Perk
tokens in `frontend/src/styles.css` — electric lime on warm parchment, layers
separated by tone rather than shadow, weights 400/500 only. Lime is a filled
surface with ink on top, never coloured text, which is why headings are ink
and the deep lime `#4f7a12` carries the small mono labels.

**Screenshots are real.** `public/shots/` is a copy of `/screenshots`, captured
from the running app on a real paper with a real review. Regenerate those
first if the UI changes, then copy them in.

## Scenes

Upload → the six parse stages → what the parser found → honest failures →
citation styles → resolution → the reader → citations as links → review →
missing work → accepting a finding → claim checks → surfaced API failures →
editing by command → the diff and integrity check → citation tokens → the
editable LaTeX view → export → architecture → running it with Docker.
