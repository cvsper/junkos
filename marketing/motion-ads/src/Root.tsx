import React from "react";
import { Composition } from "remotion";
import { TrustLocalAd } from "./TrustLocalAd";

export const Root: React.FC = () => {
  return (
    <Composition
      id="TrustLocalAd"
      component={TrustLocalAd}
      durationInFrames={210}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
