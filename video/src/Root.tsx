import React from "react";
import { Composition } from "remotion";
import { FeatureTour, TOTAL_FRAMES } from "./FeatureTour";
import { FPS } from "./theme";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="FeatureTour"
    component={FeatureTour}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
