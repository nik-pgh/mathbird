import { EvalFailure } from "../../data/retrievalEval";
import { targetDetail, targetKey, targetLabel } from "../../lib/evalMetrics";

interface Props {
  failures: readonly EvalFailure[];
}

export default function FailureList({ failures }: Props) {
  if (failures.length === 0) {
    return (
      <section className="eval-panel">
        <div className="eval-section-header">
          <div>
            <h2>Failed targets</h2>
            <p>No target failures in this report.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="eval-panel">
      <div className="eval-section-header">
        <div>
          <h2>Failed targets</h2>
          <p>Targets that did not produce retrieval metrics.</p>
        </div>
        <span className="eval-count-badge">{failures.length}</span>
      </div>

      <div className="eval-failure-list">
        {failures.map((failure) => (
          <article
            className="eval-failure-row"
            key={targetKey(failure)}
          >
            <div>
              <strong>{targetLabel(failure)}</strong>
              <span>{targetDetail(failure)}</span>
            </div>
            <code>{failure.error}</code>
          </article>
        ))}
      </div>
    </section>
  );
}
