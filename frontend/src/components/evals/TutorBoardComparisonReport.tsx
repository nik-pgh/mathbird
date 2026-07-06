import { useMemo, useState } from "react";

import type { TutorBoardEvalSource, TutorBoardEvalTarget } from "../../data/tutorBoardEval";
import { defaultTutorBoardSelection } from "../../lib/evalCatalog";
import {
  formatPassRate,
  formatTutorBoardReportTime,
  passTone,
  rankTutorBoardTargets,
  tutorBoardTargetKey,
  tutorBoardTargetLabel,
} from "../../lib/tutorBoardEvalMetrics";
import TutorBoardAxisSummaryPanel from "./TutorBoardAxisSummaryPanel";
import TutorBoardCaseMatrix from "./TutorBoardCaseMatrix";
import TutorBoardComparisonTable from "./TutorBoardComparisonTable";
import TutorBoardFailureList from "./TutorBoardFailureList";
import TutorBoardTargetPicker from "./TutorBoardTargetPicker";

interface Props {
  sources: readonly TutorBoardEvalSource[];
  targets: readonly TutorBoardEvalTarget[];
}

export default function TutorBoardComparisonReport({ sources, targets }: Props) {
  // The comparison table shows every loaded run; the detail panels (case
  // matrix + failure list) show one run at a time, selected via folder tabs.
  // Defaults to baseline when present, otherwise the ranked leader.
  const sorted = useMemo(
    () => defaultTutorBoardSelection(targets),
    [targets],
  );
  const ranked = rankTutorBoardTargets(sorted);
  const leader = ranked[0];
  const defaultKey = useMemo(() => {
    const baseline = sorted.find((item) => item.targetId === "baseline");
    return tutorBoardTargetKey(baseline ?? leader ?? sorted[0]);
  }, [sorted, leader]);

  const [activeKey, setActiveKey] = useState<string>(defaultKey);
  // If the active run is no longer loaded (e.g. its JSON was removed) or the
  // default changed, fall back to the current default.
  const effectiveKey = sorted.some((t) => tutorBoardTargetKey(t) === activeKey)
    ? activeKey
    : defaultKey;
  const active = useMemo(
    () =>
      sorted.find((t) => tutorBoardTargetKey(t) === effectiveKey) ?? leader,
    [sorted, effectiveKey, leader],
  );
  const latestSource = sources[0];

  if (!leader || sorted.length === 0) {
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
              {sorted.length} experiment{sorted.length === 1 ? "" : "s"} loaded ·{" "}
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
          <strong>{sorted.length}</strong>
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
            {sorted.some((item) => item.targetId === "baseline") ? "loaded" : "—"}
          </strong>
          <p>
            {sorted.some((item) => item.targetId === "baseline")
              ? "tutorBoardEval.baseline.generated.json"
              : "Add a baseline run with --target-id baseline"}
          </p>
        </article>
      </section>

      <TutorBoardComparisonTable targets={sorted} />
      <TutorBoardTargetPicker
        targets={sorted}
        activeKey={effectiveKey}
        onSelect={setActiveKey}
      />
      {active ? (
        <TutorBoardAxisSummaryPanel summaries={active.report.axisSummaries} />
      ) : null}
      <TutorBoardCaseMatrix targets={active ? [active] : []} />
      <TutorBoardFailureList targets={active ? [active] : []} />
    </section>
  );
}
