import type { TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import {
  tutorBoardTargetKey,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";

interface Props {
  targets: readonly TutorBoardEvalTarget[];
  selectedKeys: ReadonlySet<string>;
  onToggle: (key: string) => void;
}

/**
 * Multi-select toggle chips that filter which tutor-board runs appear in the
 * detail panels (case matrix + failure list). Renders only when more than one
 * run is loaded — with a single run there is nothing to filter.
 *
 * Reuses the retrieval-path chip styles so no new CSS is needed.
 */
export default function TutorBoardTargetPicker({
  targets,
  selectedKeys,
  onToggle,
}: Props) {
  if (targets.length < 2) {
    return null;
  }

  return (
    <div
      className="eval-path-filter"
      role="group"
      aria-label="Filter tutor board runs"
    >
      {targets.map((target) => {
        const key = tutorBoardTargetKey(target);
        const selected = selectedKeys.has(key);
        return (
          <button
            type="button"
            key={key}
            className={`eval-path-filter-button${selected ? " selected" : ""}`}
            aria-pressed={selected}
            onClick={() => onToggle(key)}
          >
            {tutorBoardTargetLabel(target)}
          </button>
        );
      })}
    </div>
  );
}
