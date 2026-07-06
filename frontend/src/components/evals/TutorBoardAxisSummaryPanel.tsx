import MetricBar from "./MetricBar";
import type { TutorBoardAxisSummary } from "../../data/tutorBoardEval";
import {
  formatPassRate,
  passTone,
  tutorBoardAxisLabel,
  TUTOR_BOARD_AXIS_HINTS,
} from "../../lib/tutorBoardEvalMetrics";

interface Props {
  summaries: readonly TutorBoardAxisSummary[];
}

export default function TutorBoardAxisSummaryPanel({ summaries }: Props) {
  const ordered = [...summaries].sort((a, b) => a.axis.localeCompare(b.axis));

  return (
    <section className="eval-panel">
      <div className="eval-section-header">
        <div>
          <h2>Axis pass rates</h2>
          <p>How the board extractor and reference rubric score on each evaluation axis.</p>
        </div>
      </div>

      <div className="eval-model-bars">
        {ordered.map((summary) => (
          <article className="eval-model-card" key={summary.axis}>
            <div className="eval-model-card-heading">
              <strong>{tutorBoardAxisLabel(summary.axis)}</strong>
              <span>
                {summary.passed}/{summary.total} passed
              </span>
            </div>
            <MetricBar
              label={tutorBoardAxisLabel(summary.axis)}
              value={formatPassRate(summary.passRate)}
              ratio={summary.passRate}
              detail={TUTOR_BOARD_AXIS_HINTS[summary.axis]}
              tone={passTone(summary.passRate)}
            />
          </article>
        ))}
      </div>
    </section>
  );
}
