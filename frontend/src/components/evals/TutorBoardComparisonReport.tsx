import { useMemo } from "react";

import type { TutorBoardEvalSource, TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import { defaultTutorBoardSelection } from "../../lib/evalCatalog";
import {
  formatPassRate,
  formatTutorBoardReportTime,
  passTone,
  rankTutorBoardTargets,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";
import TutorBoardAxisSummaryPanel from "./TutorBoardAxisSummaryPanel";
import TutorBoardCaseMatrix from "./TutorBoardCaseMatrix";
import TutorBoardComparisonTable from "./TutorBoardComparisonTable";
import TutorBoardFailureList from "./TutorBoardFailureList";

interface Props {
  sources: readonly TutorBoardEvalSource[];
  targets: readonly TutorBoardEvalTarget[];
}

export default function TutorBoardComparisonReport({ sources, targets }: Props) {
  const selected = useMemo(
    () => defaultTutorBoardSelection(targets),
    [targets],
  );
  const ranked = rankTutorBoardTargets(selected);
  const leader = ranked[0];
  const latestSource = sources[0];

  if (!leader || selected.length === 0) {
    return (
      <section className="eval-report-view" aria-label="Tutor board evaluation">
        <header className="eval-hero">
          <div>
            <p className="eval-eyebrow">Agent evaluation</p>
            <h1>Tutor board evaluation</h1>
            <p className="eval-hero-subtitle">
              <span>No tutor board eval JSON found under frontend/src/data/.</span>
            </p>
          </div>
        </header>
      </section>
    );
  }

  const caseCount = leader.report.cases.length;
  const referenceCount = leader.report.cases.filter(
    (item) => item.axis === "reference",
  ).length;

  return (
    <section className="eval-report-view" aria-label="Tutor board evaluation">
      <header className="eval-hero">
        <div>
          <p className="eval-eyebrow">Agent evaluation</p>
          <h1>Tutor board evaluation</h1>
          <p className="eval-hero-subtitle">
            <span>
              Golden-set rubric for tutor card usage, content, grouping, and board
              references.
            </span>
            <span>
              {selected.length} experiment{selected.length === 1 ? "" : "s"} loaded ·{" "}
              {caseCount} golden cases per run.
            </span>
          </p>
        </div>
        <dl className="eval-report-meta" aria-label="Report metadata">
          <div>
            <dt>Latest run</dt>
            <dd>
              {formatTutorBoardReportTime(latestSource?.report.createdAt ?? "") ||
                "Unknown run"}
            </dd>
          </div>
          <div>
            <dt>Golden set</dt>
            <dd>{leader.report.goldenPath}</dd>
          </div>
        </dl>
      </header>

      <section className="eval-summary-grid" aria-label="Evaluation summary">
        <article className="eval-summary-card">
          <span>Leader</span>
          <strong>{tutorBoardTargetLabel(leader)}</strong>
          <p className={`eval-tone-${passTone(leader.report.passRate)}`}>
            {formatPassRate(leader.report.passRate)} overall pass rate
          </p>
        </article>
        <article className="eval-summary-card">
          <span>Experiments</span>
          <strong>{selected.length}</strong>
          <p>One JSON file per tutor-board experiment run</p>
        </article>
        <article className="eval-summary-card">
          <span>Reference cases</span>
          <strong>{referenceCount}</strong>
          <p>Static utterance rubric checks per run</p>
        </article>
        <article className="eval-summary-card">
          <span>Baseline</span>
          <strong>
            {selected.some((item) => item.targetId === "baseline") ? "loaded" : "—"}
          </strong>
          <p>
            {selected.some((item) => item.targetId === "baseline")
              ? "tutorBoardEval.baseline.generated.json"
              : "Add a baseline run with --target-id baseline"}
          </p>
        </article>
      </section>

      <TutorBoardComparisonTable targets={selected} />
      {selected.length === 1 ? (
        <TutorBoardAxisSummaryPanel summaries={leader.report.axisSummaries} />
      ) : null}
      <TutorBoardCaseMatrix targets={selected} />
      <TutorBoardFailureList targets={selected} />
    </section>
  );
}
