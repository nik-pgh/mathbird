import type { TutorBoardCaseResult } from "../../data/tutorBoardEval";
import {
  summarizeActualItems,
  tutorBoardAxisLabel,
  tutorBoardCaseLabel,
} from "../../lib/tutorBoardEvalMetrics";

interface Props {
  cases: readonly TutorBoardCaseResult[];
}

export default function TutorBoardCaseMatrix({ cases }: Props) {
  return (
    <section className="eval-panel eval-case-matrix">
      <div className="eval-section-header">
        <div>
          <h2>Golden case outcomes</h2>
          <p>Pass/fail per golden row across usage, content, grouping, card kind, and reference.</p>
        </div>
        <span className="eval-count-badge">{cases.length}</span>
      </div>

      <div className="eval-table-wrap">
        <table className="eval-table eval-case-table eval-tutor-board-table">
          <thead>
            <tr>
              <th>Case</th>
              <th>Axis</th>
              <th>Scenario</th>
              <th>Result</th>
              <th>Actual cards</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => (
              <tr key={item.caseId} className={item.passed ? "" : "eval-tutor-board-row-fail"}>
                <td>
                  <code>{tutorBoardCaseLabel(item.caseId)}</code>
                </td>
                <td>
                  <span className="eval-type-badge">{tutorBoardAxisLabel(item.axis)}</span>
                </td>
                <td>{item.description || "—"}</td>
                <td>
                  <span
                    className={`eval-rank-pill ${item.passed ? "best" : "miss"}`}
                  >
                    {item.passed ? "pass" : "fail"}
                  </span>
                </td>
                <td>
                  <code>{summarizeActualItems(item.actualItems)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
