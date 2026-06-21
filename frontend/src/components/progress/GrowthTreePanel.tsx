import { useEffect, useMemo, useRef, useState } from "react";
import {
  GROWTH_STAGES,
  progressToGrowth,
  type GrowthStageIndex,
} from "../../lib/growthTree";
import { useProgressSnapshot } from "./ProgressSnapshotContext";
import "../../styles/growth-tree.css";

export default function GrowthTreePanel() {
  const snapshot = useProgressSnapshot();
  const growth = useMemo(
    () => progressToGrowth(snapshot?.summary ?? { mastered: 0, in_progress: 0, total: 0 }),
    [snapshot],
  );

  const [displayIndex, setDisplayIndex] = useState<GrowthStageIndex>(0);
  const [revealing, setRevealing] = useState(false);
  const [working, setWorking] = useState(false);
  const prevIndexRef = useRef(0);

  useEffect(() => {
    const nextIndex = growth.stageIndex;
    if (nextIndex === prevIndexRef.current) {
      setWorking(growth.stageT > 0 && growth.stageT < 1);
      return;
    }

    prevIndexRef.current = nextIndex;
    setDisplayIndex(nextIndex);
    setRevealing(true);
    setWorking(false);
  }, [growth.stageIndex, growth.stageT]);

  const stage = GROWTH_STAGES[displayIndex];

  return (
    <div
      className="growth-tree-panel"
      aria-hidden="true"
      data-stage={stage.id}
      data-working={working || undefined}
    >
      <div className="growth-tree-frame">
        <img
          key={displayIndex}
          className={`growth-tree-art${revealing ? " growth-tree-art--revealing" : ""}`}
          src={stage.src}
          alt=""
          draggable={false}
          onAnimationEnd={() => setRevealing(false)}
        />
        {working && <span className="growth-tree-sketch-shimmer" aria-hidden="true" />}
      </div>
    </div>
  );
}
