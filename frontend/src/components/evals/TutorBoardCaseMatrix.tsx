import type { TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import {
  caseActualItems,
  casePassed,
  tutorBoardAxisLabel,
  tutorBoardCaseLabel,
  tutorBoardTargetKey,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";
import ActualCardsHoverCard from "./ActualCardsHoverCard";

interface Props {
  targets: readonly TutorBoardEvalTarget[];
}

export default function TutorBoardCaseMatrix({ targets }: Props) {
  const reference = targets[0];
  if (!reference) {
    return null;
  }

  const multiTarget = targets.length > 1;

  return (
    <section className="eval-panel eval-case-matrix">
      <div className="eval-section-header">
        <div>
          <h2>Golden case outcomes</h2>
          <p>
            {multiTarget
              ? "Pass/fail per golden row across loaded tutor-board experiments."
              : "Pass/fail per golden row across usage, content, grouping, card kind, and reference."}
          </p>
        </div>
        <span className="eval-count-badge">{reference.report.cases.length}</span>
      </div>

      <div className="eval-table-wrap">
        <table className="eval-table eval-case-table eval-tutor-board-table">
          <thead>
            <tr>
              <th>Case</th>
              <th>Axis</th>
              <th>Scenario</th>
              {targets.map((target) => (
                <th key={tutorBoardTargetKey(target)}>{tutorBoardTargetLabel(target)}</th>
              ))}
              {targets.map((target) => (
                <th key={`${tutorBoardTargetKey(target)}-cards`}>
                  {multiTarget ? `${tutorBoardTargetLabel(target)} cards` : "Actual cards"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reference.report.cases.map((item) => {
              const rowFailed = targets.some(
                (target) => casePassed(target.report, item.caseId) === false,
              );
              return (
                <tr
                  key={item.caseId}
                  className={rowFailed ? "eval-tutor-board-row-fail" : ""}
                >
                  <td>
                    <code>{tutorBoardCaseLabel(item.caseId)}</code>
                  </td>
                  <td>
                    <span className="eval-type-badge">{tutorBoardAxisLabel(item.axis)}</span>
                  </td>
                  <td>{item.description || "—"}</td>
                  {targets.map((target) => {
                    const passed = casePassed(target.report, item.caseId);
                    return (
                      <td key={tutorBoardTargetKey(target)}>
                        {passed === null ? (
                          "—"
                        ) : (
                          <span
                            className={`eval-rank-pill ${passed ? "best" : "miss"}`}
                          >
                            {passed ? "pass" : "fail"}
                          </span>
                        )}
                      </td>
                    );
                  })}
                  {targets.map((target) => (
                    <td key={`${tutorBoardTargetKey(target)}-cards`}>
                      <ActualCardsHoverCard
                        items={caseActualItems(target.report, item.caseId)}
                      />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
