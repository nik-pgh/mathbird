import type { ProgressSummary } from "./progress";

import stage01 from "../assets/growth-tree/stage-01-seed.png";
import stage02 from "../assets/growth-tree/stage-02-sprout.png";
import stage03 from "../assets/growth-tree/stage-03-sapling.png";
import stage04 from "../assets/growth-tree/stage-04-juvenile.png";
import stage05 from "../assets/growth-tree/stage-05-adult.png";
import stage06 from "../assets/growth-tree/stage-06-flowers.png";
import stage07 from "../assets/growth-tree/stage-07-fruits.png";
import stage08 from "../assets/growth-tree/stage-08-nest.png";
import stage09 from "../assets/growth-tree/stage-09-bird.png";
import stage10 from "../assets/growth-tree/stage-10-flock.png";

export const GROWTH_STAGES = [
  { id: "seed", label: "Seed", src: stage01 },
  { id: "sprout", label: "Sprout", src: stage02 },
  { id: "sapling", label: "Sapling", src: stage03 },
  { id: "juvenile", label: "Young tree", src: stage04 },
  { id: "adult", label: "Mature tree", src: stage05 },
  { id: "flowers", label: "Blossoms", src: stage06 },
  { id: "fruits", label: "Fruit", src: stage07 },
  { id: "nest", label: "Nest", src: stage08 },
  { id: "bird", label: "First bird", src: stage09 },
  { id: "flock", label: "Flock", src: stage10 },
] as const;

export type GrowthStageIndex = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;

export interface GrowthProgress {
  stageIndex: GrowthStageIndex;
  /** 0–1 progress within the current stage. */
  stageT: number;
}

const STAGE_COUNT = GROWTH_STAGES.length;

/** Map mastered-problem ratio to a growth stage (and in-stage progress). */
export function progressToGrowth(summary: ProgressSummary): GrowthProgress {
  if (summary.total <= 0) {
    return { stageIndex: 0, stageT: 0 };
  }

  const masteredRatio = summary.mastered / summary.total;
  const inProgressHint =
    summary.in_progress > 0 && summary.mastered < summary.total ? 0.12 : 0;
  const scaled = Math.min(STAGE_COUNT, (masteredRatio + inProgressHint) * STAGE_COUNT);
  const index = Math.min(STAGE_COUNT - 1, Math.floor(scaled));

  return {
    stageIndex: index as GrowthStageIndex,
    stageT: scaled - index,
  };
}
