import type { TutorBoardCaseFailure, TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import {
  tutorBoardAxisLabel,
  tutorBoardCaseLabel,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";

interface Props {
  targets: readonly TutorBoardEvalTarget[];
}

interface CombinedFailure extends TutorBoardCaseFailure {
  targetId: string;
  targetLabel: string;
}

function collectFailures(targets: readonly TutorBoardEvalTarget[]): CombinedFailure[] {
  const combined: CombinedFailure[] = [];
  for (const target of targets) {
    for (const failure of target.report.failures) {
      combined.push({
        ...failure,
        targetId: target.targetId,
        targetLabel: tutorBoardTargetLabel(target),
      });
    }
  }
  return combined.sort((a, b) => {
    if (a.caseId !== b.caseId) {
      return a.caseId.localeCompare(b.caseId);
    }
    return a.targetLabel.localeCompare(b.targetLabel);
  });
}

export default function TutorBoardFailureList({ targets }: Props) {
  const failures = collectFailures(targets);
  const multiTarget = targets.length > 1;

  if (failures.length === 0) {
    return (
      <section className="eval-panel">
        <div className="eval-section-header">
          <div>
            <h2>Failed cases</h2>
            <p>All golden cases passed across loaded experiments.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="eval-panel">
      <div className="eval-section-header">
        <div>
          <h2>Failed cases</h2>
          <p>Rubric mismatches from the board extractor or reference utterance checks.</p>
        </div>
        <span className="eval-count-badge">{failures.length}</span>
      </div>

      <div className="eval-failure-list">
        {failures.map((failure) => (
          <article
            className="eval-failure-row"
            key={`${failure.targetId}-${failure.caseId}-${failure.failures.join("|")}`}
          >
            <div>
              <strong>
                {multiTarget ? (
                  <>
                    <span className="eval-type-badge">{failure.targetLabel}</span>{" "}
                  </>
                ) : null}
                <code>{tutorBoardCaseLabel(failure.caseId)}</code> ·{" "}
                {tutorBoardAxisLabel(failure.axis)}
              </strong>
              <span>{failure.description || "No description"}</span>
            </div>
            <code>{failure.failures.join(" · ")}</code>
          </article>
        ))}
      </div>
    </section>
  );
}
