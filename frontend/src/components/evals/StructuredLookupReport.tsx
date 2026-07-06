import { useMemo, useState } from "react";

import CaseOutcomeMatrix from "./CaseOutcomeMatrix";
import FailureList from "./FailureList";
import ModelComparisonTable from "./ModelComparisonTable";
import StructuredPathBreakdown from "./StructuredPathBreakdown";
import {
  type StructuredEvalPolicyGroup,
  type StructuredRetrievalPath,
  buildStructuredComparisonReport,
  productionTargetsFromGroups,
  targetsForRetrievalPath,
  type EvalReportSource,
} from "../../lib/evalCatalog";
import {
  formatLatency,
  formatPercent,
  formatReportTime,
  formatScore,
  goldenSetSummary,
  rankTargets,
  targetLabel,
} from "../../lib/evalMetrics";

interface Props {
  policyGroups: readonly StructuredEvalPolicyGroup[];
  sources: readonly EvalReportSource[];
}

export default function StructuredLookupReport({ policyGroups, sources }: Props) {
  const [matrixPath, setMatrixPath] = useState<StructuredRetrievalPath>("production");

  const report = useMemo(
    () =>
      buildStructuredComparisonReport(
        productionTargetsFromGroups(policyGroups),
        sources,
      ),
    [policyGroups, sources],
  );

  const matrixReport = useMemo(
    () =>
      buildStructuredComparisonReport(
        targetsForRetrievalPath(policyGroups, matrixPath),
        sources,
      ),
    [policyGroups, sources, matrixPath],
  );

  if (!report || report.targets.length === 0) {
    return (
      <section className="eval-report-view" aria-label="Structured lookup comparison">
        <header className="eval-hero">
          <div>
            <p className="eval-eyebrow">Retrieval evaluation</p>
            <h1>Structured lookup comparison</h1>
            <p className="eval-hero-subtitle">
              <span>No structured eval JSON found under frontend/src/data/.</span>
            </p>
          </div>
        </header>
      </section>
    );
  }

  const rankedTargets = rankTargets(report.targets);
  const bestTarget = rankedTargets[0];
  const fastestTarget = [...report.targets].sort(
    (a, b) => a.metrics.avgLatencyMs - b.metrics.avgLatencyMs,
  )[0];

  return (
    <section className="eval-report-view" aria-label="Structured lookup comparison">
      <header className="eval-hero">
        <div>
          <p className="eval-eyebrow">Retrieval evaluation</p>
          <h1>Structured lookup comparison</h1>
          <p className="eval-hero-subtitle">
            <span>Goodfellow chapter 2 structured golden set.</span>
            <span>
              Top K {report.topK}. {report.targets.length} chunk{" "}
              {report.targets.length === 1 ? "policy" : "policies"} on production retrieve().
            </span>
          </p>
        </div>
        <dl className="eval-report-meta" aria-label="Report metadata">
          <div>
            <dt>Latest run</dt>
            <dd>{formatReportTime(report.createdAt)}</dd>
          </div>
          <div>
            <dt>Golden set</dt>
            <dd>{report.goldenPath}</dd>
          </div>
        </dl>
      </header>

      <section className="eval-summary-grid" aria-label="Evaluation summary">
        <article className="eval-summary-card">
          <span>Leader</span>
          <strong>{targetLabel(bestTarget)}</strong>
          <p>
            {formatPercent(bestTarget.metrics.hitAt1)} Hit@1,{" "}
            {formatScore(bestTarget.metrics.mrr)} MRR
          </p>
        </article>
        <article className="eval-summary-card">
          <span>Fastest</span>
          <strong>{targetLabel(fastestTarget)}</strong>
          <p>{formatLatency(fastestTarget.metrics.avgLatencyMs)} average retrieval</p>
        </article>
        <article className="eval-summary-card">
          <span>Golden cases</span>
          <strong>{bestTarget.caseCount}</strong>
          <p>{goldenSetSummary(report.comparisonAxis)}</p>
        </article>
        <article className="eval-summary-card">
          <span>Chunk policies</span>
          <strong>{policyGroups.length}</strong>
          <p>One JSON report file per indexed collection snapshot</p>
        </article>
      </section>

      <ModelComparisonTable
        targets={report.targets}
        targetColumnLabel="Chunk policy (production)"
      />
      <StructuredPathBreakdown groups={policyGroups} />
      {matrixReport ? (
        <CaseOutcomeMatrix
          report={matrixReport}
          targets={rankTargets(matrixReport.targets)}
          retrievalPath={matrixPath}
          onRetrievalPathChange={setMatrixPath}
        />
      ) : null}
      <FailureList failures={report.failures} />
    </section>
  );
}
