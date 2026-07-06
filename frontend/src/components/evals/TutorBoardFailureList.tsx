import type { TutorBoardCaseFailure } from "../../data/tutorBoardEval";
import {
  tutorBoardAxisLabel,
  tutorBoardCaseLabel,
} from "../../lib/tutorBoardEvalMetrics";

interface Props {
  failures: readonly TutorBoardCaseFailure[];
}

export default function TutorBoardFailureList({ failures }: Props) {
  if (failures.length === 0) {
    return (
      <section className="eval-panel">
        <div className="eval-section-header">
          <div>
            <h2>Failed cases</h2>
            <p>All golden cases passed in this report.</p>
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
          <article className="eval-failure-row" key={failure.caseId}>
            <div>
              <strong>
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
