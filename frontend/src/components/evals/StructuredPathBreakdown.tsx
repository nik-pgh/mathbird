import type { StructuredEvalPolicyGroup } from "../../lib/evalCatalog";
import { formatLatency, formatPercent, formatScore } from "../../lib/evalMetrics";
import { retrievalPathLabel } from "../../lib/evalCatalog";

interface Props {
  groups: readonly StructuredEvalPolicyGroup[];
}

export default function StructuredPathBreakdown({ groups }: Props) {
  if (groups.length === 0) {
    return null;
  }

  return (
    <section className="eval-path-breakdown" aria-label="Retrieval path breakdown per chunk policy">
      <header className="eval-path-breakdown-header">
        <h2>Retrieval path breakdown</h2>
        <p>Production, structured-only, and semantic-only paths within each chunk policy.</p>
      </header>
      <div className="eval-path-breakdown-grid">
        {groups.map((group) => (
          <article className="eval-path-breakdown-card" key={group.sourceId}>
            <h3>{group.policyLabel}</h3>
            <p className="eval-path-breakdown-meta">{group.embedding}</p>
            <table className="eval-path-breakdown-table">
              <thead>
                <tr>
                  <th scope="col">Path</th>
                  <th scope="col">Hit@1</th>
                  <th scope="col">Hit@3</th>
                  <th scope="col">MRR</th>
                  <th scope="col">Latency</th>
                </tr>
              </thead>
              <tbody>
                {group.paths.map((entry) => (
                  <tr key={entry.catalogId}>
                    <th scope="row">{retrievalPathLabel(entry.facets.retrievalPath)}</th>
                    <td>{formatPercent(entry.target.metrics.hitAt1)}</td>
                    <td>{formatPercent(entry.target.metrics.hitAt3)}</td>
                    <td>{formatScore(entry.target.metrics.mrr)}</td>
                    <td>{formatLatency(entry.target.metrics.avgLatencyMs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </article>
        ))}
      </div>
    </section>
  );
}
