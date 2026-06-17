import MetricBar from "./MetricBar";
import { EvalTarget } from "../../data/retrievalEval";
import {
  formatLatency,
  formatPercent,
  formatScore,
  comparisonTitle,
  rankTargets,
  targetDetail,
  targetKey,
  targetLabel,
} from "../../lib/evalMetrics";

interface Props {
  targets: readonly EvalTarget[];
}

export default function ModelComparisonTable({ targets }: Props) {
  const ranked = rankTargets(targets);
  const maxLatency = Math.max(1, ...ranked.map((target) => target.metrics.avgLatencyMs));
  const axis = ranked[0]?.comparisonAxis ?? "embedding_model";
  const targetHeading = axis === "chunk_policy" ? "Policy" : "Target";

  return (
    <section className="eval-panel eval-ranking">
      <div className="eval-section-header">
        <div>
          <h2>{comparisonTitle(axis)}</h2>
          <p>Sorted by Hit@3, MRR, Hit@5, then latency.</p>
        </div>
      </div>

      <div className="eval-table-wrap">
        <table className="eval-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>{targetHeading}</th>
              <th>Hit@1</th>
              <th>Hit@3</th>
              <th>MRR</th>
              <th>Content</th>
              <th>Latency</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((target, index) => (
              <tr key={targetKey(target)}>
                <td className="eval-rank-cell">{index + 1}</td>
                <td>
                  <div className="eval-model-cell">
                    <strong>{targetLabel(target)}</strong>
                    <span>{targetDetail(target)}</span>
                    <code>{target.collectionName}</code>
                  </div>
                </td>
                <td>{formatPercent(target.metrics.hitAt1)}</td>
                <td>{formatPercent(target.metrics.hitAt3)}</td>
                <td>{formatScore(target.metrics.mrr)}</td>
                <td>{formatPercent(target.metrics.avgContentMatch)}</td>
                <td>{formatLatency(target.metrics.avgLatencyMs)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="eval-model-bars">
        {ranked.map((target) => (
          <article className="eval-model-card" key={targetKey(target)}>
            <div className="eval-model-card-heading">
              <strong>{targetLabel(target)}</strong>
              <span>{targetDetail(target)}</span>
            </div>
            <MetricBar
              label="Hit@1"
              value={formatPercent(target.metrics.hitAt1)}
              ratio={target.metrics.hitAt1}
            />
            <MetricBar
              label="MRR"
              value={formatScore(target.metrics.mrr)}
              ratio={target.metrics.mrr}
            />
            <MetricBar
              label="Content"
              value={formatPercent(target.metrics.avgContentMatch)}
              ratio={target.metrics.avgContentMatch}
              tone="neutral"
            />
            <MetricBar
              label="Latency"
              value={formatLatency(target.metrics.avgLatencyMs)}
              ratio={target.metrics.avgLatencyMs / maxLatency}
              tone="warn"
            />
          </article>
        ))}
      </div>
    </section>
  );
}
