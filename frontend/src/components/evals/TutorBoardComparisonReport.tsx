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
  // All runs are shown by default; the user narrows the detail panels (case
  // matrix + failure list) via the picker. The comparison table stays the
  // all-runs overview.
  const sorted = useMemo(
    () => defaultTutorBoardSelection(targets),
    [targets],
  );
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(
    () => new Set(sorted.map(tutorBoardTargetKey)),
  );

  // The detail selection is the user's choice intersected with currently
  // loaded runs (so removed JSON files don't leave stale keys). `toggleKey`
  // guarantees the set never goes fully empty.
  const sortedKeys = useMemo(
    () => new Set(sorted.map(tutorBoardTargetKey)),
    [sorted],
  );
  const effectiveKeys = useMemo(() => {
    const next = new Set<string>();
    for (const key of selectedKeys) {
      if (sortedKeys.has(key)) next.add(key);
    }
    return next.size > 0 ? next : sortedKeys;
  }, [selectedKeys, sortedKeys]);

  const selected = useMemo(
    () => sorted.filter((target) => effectiveKeys.has(tutorBoardTargetKey(target))),
    [sorted, effectiveKeys],
  );
  const ranked = rankTutorBoardTargets(sorted);
  const leader = ranked[0];
  const latestSource = sources[0];

  const toggleKey = (key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      // Never let the detail selection go fully empty — that would blank the
      // case matrix and failure list. Keep at least one run selected.
      if (next.size === 0) {
        return new Set(sortedKeys);
      }
      return next;
    });
  };

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
        selectedKeys={effectiveKeys}
        onToggle={toggleKey}
      />
      {selected.length === 1 ? (
        <TutorBoardAxisSummaryPanel summaries={selected[0].report.axisSummaries} />
      ) : null}
      <TutorBoardCaseMatrix targets={selected} />
      <TutorBoardFailureList targets={selected} />
    </section>
  );
}
