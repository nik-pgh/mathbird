import { useMemo, useState } from "react";

import CaseOutcomeMatrix from "./CaseOutcomeMatrix";
import FailureList from "./FailureList";
import ModelComparisonTable from "./ModelComparisonTable";
import StructuredConfigPicker from "./StructuredConfigPicker";
import {
  StructuredEvalTarget,
  buildStructuredComparisonReport,
  defaultStructuredSelection,
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

function toggleSelected(
  selected: StructuredEvalTarget[],
  catalogId: string,
  catalog: readonly StructuredEvalTarget[],
): StructuredEvalTarget[] {
  const item = catalog.find((entry) => entry.catalogId === catalogId);
  if (!item) {
    return [...selected];
  }
  const exists = selected.some((entry) => entry.catalogId === catalogId);
  if (exists) {
    const next = selected.filter((entry) => entry.catalogId !== catalogId);
    return next.length > 0 ? next : selected;
  }
  return [...selected, item].sort((a, b) => a.shortLabel.localeCompare(b.shortLabel));
}

interface Props {
  catalog: readonly StructuredEvalTarget[];
  sources: readonly EvalReportSource[];
}

export default function StructuredLookupReport({ catalog, sources }: Props) {
  const [selected, setSelected] = useState(() => defaultStructuredSelection(catalog));

  const report = useMemo(
    () => buildStructuredComparisonReport(selected, sources),
    [selected, sources],
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
              Top K {report.topK}. {selected.length} configuration
              {selected.length === 1 ? "" : "s"} selected.
            </span>
          </p>
          <StructuredConfigPicker
            catalog={catalog}
            selectedIds={selected.map((item) => item.catalogId)}
            onToggle={(catalogId) =>
              setSelected((current) => toggleSelected(current, catalogId, catalog))
            }
          />
        </div>
        <dl className="eval-report-meta" aria-label="Report metadata">
          <div>
            <dt>Latest run</dt>
            <dd>{formatReportTime(report.createdAt)}</dd>
          </div>
          <div>
            <dt>Sources</dt>
            <dd>{sources.length} JSON file(s)</dd>
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
          <span>Available configs</span>
          <strong>{catalog.length}</strong>
          <p>Toggle chunk policy and retrieval path above</p>
        </article>
      </section>

      <ModelComparisonTable
        targets={report.targets}
        targetColumnLabel="Configuration"
      />
      <CaseOutcomeMatrix
        report={report}
        targets={rankedTargets}
        targetHeader={(target) => target.label}
      />
      <FailureList failures={report.failures} />
    </section>
  );
}
