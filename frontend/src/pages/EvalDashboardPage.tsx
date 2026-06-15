import CaseOutcomeMatrix from "../components/evals/CaseOutcomeMatrix";
import FailureList from "../components/evals/FailureList";
import ModelComparisonTable from "../components/evals/ModelComparisonTable";
import SessionTopbar from "../components/session/SessionTopbar";
import { retrievalEvalReport } from "../data/retrievalEval";
import {
  formatLatency,
  formatPercent,
  formatReportTime,
  formatScore,
  rankTargets,
} from "../lib/evalMetrics";

export default function EvalDashboardPage() {
  const report = retrievalEvalReport;
  const rankedTargets = rankTargets(report.targets);
  const bestTarget = rankedTargets[0];
  const fastestTarget = [...report.targets].sort(
    (a, b) => a.metrics.avgLatencyMs - b.metrics.avgLatencyMs,
  )[0];

  return (
    <>
      <SessionTopbar />
      <main className="eval-main">
        <section className="eval-dashboard">
          <header className="eval-hero">
            <div>
              <p className="eval-eyebrow">Retrieval evaluation</p>
              <h1>Embedding model comparison</h1>
              <p className="eval-hero-subtitle">
                <span>Goodfellow chapter 2 golden set.</span>
                <span>
                  Top K {report.topK}. {report.targets.length} successful targets.
                </span>
              </p>
            </div>
            <dl className="eval-report-meta" aria-label="Report metadata">
              <div>
                <dt>Report</dt>
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
              <strong>{bestTarget.model}</strong>
              <p>
                {formatPercent(bestTarget.metrics.hitAt1)} Hit@1,{" "}
                {formatScore(bestTarget.metrics.mrr)} MRR
              </p>
            </article>
            <article className="eval-summary-card">
              <span>Fastest</span>
              <strong>{fastestTarget.model}</strong>
              <p>{formatLatency(fastestTarget.metrics.avgLatencyMs)} average retrieval</p>
            </article>
            <article className="eval-summary-card">
              <span>Golden cases</span>
              <strong>{bestTarget.caseCount}</strong>
              <p>Definitions, formulas, figures, concepts, student-style prompts</p>
            </article>
            <article className="eval-summary-card">
              <span>Failed targets</span>
              <strong>{report.failures.length}</strong>
              <p>Missing or unavailable embedding collections</p>
            </article>
          </section>

          <ModelComparisonTable targets={report.targets} />
          <CaseOutcomeMatrix report={report} targets={rankedTargets} />
          <FailureList failures={report.failures} />
        </section>
      </main>
    </>
  );
}
