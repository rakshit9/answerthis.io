import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Overview, Title } from "./scenes/Intro";
import {
  Pipeline,
  ParseResult,
  Reader,
  Resolve,
  Tokens,
  Upload,
} from "./scenes/Parse";
import { ClaimChecks, MissingWork, ReviewRun } from "./scenes/Review";
import { EditCommand, EditDiff, Export } from "./scenes/Edit";
import { Architecture, Outro, RunIt } from "./scenes/Outro";
import {
  CitationClick,
  CiteThis,
  Failures,
  Honesty,
  LatexEdit,
  Styles,
} from "./scenes/Features";
import { FPS, OVERLAP, TAIL_SECONDS, theme } from "./theme";
import durations from "../public/vo/durations.json";

type SceneDef = {
  /** Also the narration key and the /vo/<id>.wav filename. */
  id: string;
  Component: React.FC<{ durationInFrames: number }>;
  /** Extra seconds beyond the voice-over, when a scene needs to breathe. */
  extra?: number;
};

/** Order is the story: what it is → parse → read → review → edit → ship. */
const SCENES: SceneDef[] = [
  { id: "title", Component: Title, extra: 0.6 },
  { id: "overview", Component: Overview },
  { id: "upload", Component: Upload },
  { id: "pipeline", Component: Pipeline, extra: 1.2 },
  { id: "parseResult", Component: ParseResult },
  { id: "honesty", Component: Honesty, extra: 0.6 },
  { id: "styles", Component: Styles, extra: 0.8 },
  { id: "resolve", Component: Resolve },
  { id: "reader", Component: Reader },
  { id: "citationClick", Component: CitationClick, extra: 0.8 },
  { id: "reviewRun", Component: ReviewRun },
  { id: "missingWork", Component: MissingWork },
  { id: "citeThis", Component: CiteThis, extra: 0.6 },
  { id: "claimChecks", Component: ClaimChecks },
  { id: "failures", Component: Failures, extra: 0.6 },
  { id: "editCommand", Component: EditCommand },
  { id: "editDiff", Component: EditDiff, extra: 0.6 },
  { id: "tokens", Component: Tokens },
  { id: "latex", Component: LatexEdit, extra: 0.6 },
  { id: "export", Component: Export },
  { id: "architecture", Component: Architecture },
  { id: "runIt", Component: RunIt, extra: 0.8 },
  { id: "outro", Component: Outro, extra: 1.4 },
];

/** Scene length comes from its narration, so picture and words stay in step
 *  no matter how the script is edited. */
const framesFor = (s: SceneDef) => {
  const spoken = (durations as Record<string, number>)[s.id] ?? 5;
  return Math.round((spoken + TAIL_SECONDS + (s.extra ?? 0)) * FPS);
};

export const TIMELINE = SCENES.map((s) => ({ ...s, duration: framesFor(s) }));

export const TOTAL_FRAMES = TIMELINE.reduce(
  (acc, s) => acc + s.duration - OVERLAP,
  OVERLAP,
);

export const FeatureTour: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg }}>
      {TIMELINE.map((scene) => {
        const start = from;
        from += scene.duration - OVERLAP;
        return (
          <Sequence
            key={scene.id}
            from={start}
            durationInFrames={scene.duration}
            name={scene.id}
          >
            <scene.Component durationInFrames={scene.duration} />
            {/* The voice starts a beat after the scene does, so the first
                word lands once the picture has settled. */}
            <Sequence from={Math.round(0.25 * FPS)}>
              <Audio src={staticFile(`vo/${scene.id}.wav`)} />
            </Sequence>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
