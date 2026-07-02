import { useEffect, useMemo, useState } from "react";

import CaseOutcomeMatrix from "../components/evals/CaseOutcomeMatrix";
import FailureList from "../components/evals/FailureList";
import ModelComparisonTable from "../components/evals/ModelComparisonTable";
import StructuredLookupReport from "../components/evals/StructuredLookupReport";
import SessionTopbar from "../components/session/SessionTopbar";
import {
  RetrievalEvalReport,
  RetrievalEvalReportTab,
  loadEvalCatalog,
} from "../data/retrievalEval";
import type { EvalCatalog } from "../lib/evalCatalog";
import {
  formatLatency,
  formatPercent,
  formatReportTime,
  formatScore,
  comparisonTitle,
  failureSummary,
  goldenSetSummary,
  rankTargets,
  targetLabel,
} from "../lib/evalMetrics";

function ReportView({ report }: { report: RetrievalEvalReport }) {
  const rankedTargets = rankTargets(report.targets);
  const bestTarget = rankedTargets[0];
  const fastestTarget = [...report.targets].sort(
    (a, b) => a.metrics.avgLatencyMs - b.metrics.avgLatencyMs,
  )[0];
  const reportTitle = comparisonTitle(report.comparisonAxis);

  if (!bestTarget || !fastestTarget) {
    return (
      <section className="eval-report-view" aria-label={reportTitle}>
        <header className="eval-hero">
          <div>
            <p className="eval-eyebrow">Retrieval evaluation</p>
            <h1>{reportTitle}</h1>
            <p className="eval-hero-subtitle">
              <span>No successful targets in this report.</span>
            </p>
          </div>
        </header>
        <FailureList failures={report.failures} />
      </section>
    );
  }

  return (
    <section className="eval-report-view" aria-label={reportTitle}>
      <header className="eval-hero">
        <div>
          <p className="eval-eyebrow">Retrieval evaluation</p>
          <h1>{reportTitle}</h1>
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
          <span>Failed targets</span>
          <strong>{report.failures.length}</strong>
          <p>{failureSummary(report.comparisonAxis)}</p>
        </article>
      </section>

      <ModelComparisonTable targets={report.targets} />
      <CaseOutcomeMatrix report={report} targets={rankedTargets} />
      <FailureList failures={report.failures} />
    </section>
  );
}

function reportTabLabel(tab: RetrievalEvalReportTab): string {
  return `${tab.label} (${tab.report.targets.length})`;
}

export default function EvalDashboardPage() {
  const [catalog, setCatalog] = useState<EvalCatalog | null>(null);
  const [activeTabId, setActiveTabId] = useState("structured");

  useEffect(() => {
    let cancelled = false;
    loadEvalCatalog()
      .then((loaded) => {
        if (cancelled) return;
        setCatalog(loaded);
        setActiveTabId(loaded.retrievalEvalReports[0]?.id ?? "structured");
      })
      .catch(() => {
        if (!cancelled) {
          setCatalog({
            structuredEvalSources: [],
            structuredEvalCatalog: [],
            retrievalEvalReports: [],
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const retrievalEvalReports = catalog?.retrievalEvalReports ?? [];
  const activeTab = useMemo(
    () =>
      retrievalEvalReports.find((tab) => tab.id === activeTabId) ??
      retrievalEvalReports[0],
    [activeTabId, retrievalEvalReports],
  );

  if (!catalog) {
    return (
      <>
        <SessionTopbar />
        <main className="eval-main">
          <p className="route-fallback" aria-busy="true">
            Loading evaluation reports…
          </p>
        </main>
      </>
    );
  }

  return (
    <>
      <SessionTopbar />
      <main className="eval-main">
        <section className="eval-dashboard">
          <div className="eval-tabs" role="tablist" aria-label="Evaluation reports">
            {retrievalEvalReports.map((tab) => (
              <button
                type="button"
                role="tab"
                id={`eval-tab-${tab.id}`}
                aria-selected={tab.id === activeTabId}
                aria-controls={`eval-panel-${tab.id}`}
                className="eval-tab-button"
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
              >
                {reportTabLabel(tab)}
              </button>
            ))}
          </div>
          <div
            id={`eval-panel-${activeTabId}`}
            role="tabpanel"
            aria-labelledby={`eval-tab-${activeTabId}`}
          >
            {activeTabId === "structured" ? (
              <StructuredLookupReport
                catalog={catalog.structuredEvalCatalog}
                sources={catalog.structuredEvalSources}
              />
            ) : activeTab ? (
              <ReportView report={activeTab.report} />
            ) : null}
          </div>
        </section>
      </main>
    </>
  );
}
