import { EvalTarget, RetrievalEvalReport } from "../../data/retrievalEval";
import { caseSummaries, targetKey, targetLabel } from "../../lib/evalMetrics";

interface Props {
  report: RetrievalEvalReport;
  targets: readonly EvalTarget[];
}

export default function CaseOutcomeMatrix({ report, targets }: Props) {
  const cases = caseSummaries(report);

  return (
    <section className="eval-panel eval-case-matrix">
      <div className="eval-section-header">
        <div>
          <h2>Golden case outcomes</h2>
          <p>Cells show the best matching rank returned for each question.</p>
        </div>
      </div>

      <div className="eval-table-wrap">
        <table className="eval-table eval-case-table">
          <thead>
            <tr>
              <th>Case</th>
              <th>Type</th>
              <th>Question focus</th>
              {targets.map((target) => (
                <th key={targetKey(target)}>{targetLabel(target)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => (
              <tr key={item.caseId}>
                <td>
                  <code>{item.caseId.replace("goodfellow-ch2-", "#")}</code>
                </td>
                <td>
                  <span className="eval-type-badge">{item.queryType}</span>
                </td>
                <td>{item.label}</td>
                {item.results.map((result) => (
                  <td key={result.targetKey}>
                    <span
                      className={`eval-rank-pill ${
                        result.hitAt1
                          ? "best"
                          : result.hitAt3
                          ? "ok"
                          : "miss"
                      }`}
                      title={`Content match: ${Math.round(
                        result.contentMatchRatio * 100,
                      )}%`}
                    >
                      {result.bestRank ? `@${result.bestRank}` : "miss"}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
