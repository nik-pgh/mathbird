import type { TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import {
  tutorBoardTargetKey,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";

interface Props {
  targets: readonly TutorBoardEvalTarget[];
  activeKey: string;
  onSelect: (key: string) => void;
}

/**
 * Single-select folder-tab switcher for the tutor-board detail panels (case
 * matrix + failure list). One run is active at a time; the comparison table
 * above remains the all-runs overview. Renders only when more than one run
 * is loaded — with a single run there is nothing to switch.
 *
 * Uses the eval tab styles (`.eval-tab-button`) so the active tab connects
 * to the panel below it like a folder tab.
 */
export default function TutorBoardTargetPicker({
  targets,
  activeKey,
  onSelect,
}: Props) {
  if (targets.length < 2) {
    return null;
  }

  return (
    <div className="eval-tabs eval-board-target-tabs" role="tablist" aria-label="Tutor board run">
      {targets.map((target) => {
        const key = tutorBoardTargetKey(target);
        const selected = key === activeKey;
        return (
          <button
            type="button"
            role="tab"
            key={key}
            aria-selected={selected}
            className="eval-tab-button"
            onClick={() => onSelect(key)}
          >
            {tutorBoardTargetLabel(target)}
          </button>
        );
      })}
    </div>
  );
}
