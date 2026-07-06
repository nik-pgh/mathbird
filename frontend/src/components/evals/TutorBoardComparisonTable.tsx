import MetricBar from "./MetricBar";
import type { TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import { TUTOR_BOARD_AXIS_LABELS } from "../../lib/tutorBoardEvalMetrics";
import {
  axisPassRate,
  formatPassRate,
  passTone,
  rankTutorBoardTargets,
  tutorBoardTargetDetail,
  tutorBoardTargetKey,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";
import { formatReportTime } from "../../lib/evalMetrics";

interface Props {
  targets: readonly TutorBoardEvalTarget[];
}

export default function TutorBoardComparisonTable({ targets }: Props) {
  const ranked = rankTutorBoardTargets(targets);
  const axes = Object.keys(TUTOR_BOARD_AXIS_LABELS) as Array<
    keyof typeof TUTOR_BOARD_AXIS_LABELS
  >;

  return (
    <section className="eval-panel eval-ranking">
      <div className="eval-section-header">
        <div>
          <h2>Experiment comparison</h2>
          <p>
            One JSON report per tutor-board experiment. Sorted by overall pass rate,
            then failure count.
          </p>
        </div>
      </div>

      <div className="eval-table-wrap">
        <table className="eval-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Experiment</th>
              <th>Pass rate</th>
              {axes.map((axis) => (
                <th key={axis}>{TUTOR_BOARD_AXIS_LABELS[axis]}</th>
              ))}
              <th>Failures</th>
              <th>Run</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((target, index) => (
              <tr key={tutorBoardTargetKey(target)}>
                <td className="eval-rank-cell">{index + 1}</td>
                <td>
                  <div className="eval-model-cell">
                    <strong>{tutorBoardTargetLabel(target)}</strong>
                    <span>{tutorBoardTargetDetail(target)}</span>
                    <code>{target.sourceFileName}</code>
                  </div>
                </td>
                <td>{formatPassRate(target.report.passRate)}</td>
                {axes.map((axis) => (
                  <td key={axis}>{formatPassRate(axisPassRate(target.report, axis))}</td>
                ))}
                <td>{target.report.failures.length}</td>
                <td>{formatReportTime(target.report.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="eval-model-bars">
        {ranked.map((target) => (
          <article className="eval-model-card" key={tutorBoardTargetKey(target)}>
            <div className="eval-model-card-heading">
              <strong>{tutorBoardTargetLabel(target)}</strong>
              <span>{tutorBoardTargetDetail(target)}</span>
            </div>
            <MetricBar
              label="Overall"
              value={formatPassRate(target.report.passRate)}
              ratio={target.report.passRate}
              tone={passTone(target.report.passRate)}
            />
            {axes.map((axis) => {
              const rate = axisPassRate(target.report, axis);
              return (
                <MetricBar
                  key={axis}
                  label={TUTOR_BOARD_AXIS_LABELS[axis]}
                  value={formatPassRate(rate)}
                  ratio={rate}
                  tone={passTone(rate)}
                />
              );
            })}
          </article>
        ))}
      </div>
    </section>
  );
}
