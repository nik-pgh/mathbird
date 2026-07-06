import type { TutorBoardEvalReport } from "../../data/tutorBoardEval";
import {
  formatPassRate,
  formatTutorBoardReportTime,
  passTone,
  reportHeroSubtitle,
} from "../../lib/tutorBoardEvalMetrics";
import TutorBoardAxisSummaryPanel from "./TutorBoardAxisSummaryPanel";
import TutorBoardCaseMatrix from "./TutorBoardCaseMatrix";
import TutorBoardFailureList from "./TutorBoardFailureList";

interface Props {
  report: TutorBoardEvalReport;
}

export default function TutorBoardEvalReportView({ report }: Props) {
  const passedCount = report.cases.filter((item) => item.passed).length;
  const referenceCount = report.cases.filter((item) => item.axis === "reference").length;
  const extractorCount = report.cases.length - referenceCount;

  return (
    <section className="eval-report-view" aria-label="Tutor board evaluation">
      <header className="eval-hero">
        <div>
          <p className="eval-eyebrow">Agent evaluation</p>
          <h1>Tutor board evaluation</h1>
          <p className="eval-hero-subtitle">
            <span>Golden-set rubric for tutor card usage, content, grouping, and board references.</span>
            <span>{reportHeroSubtitle(report)}</span>
          </p>
        </div>
        <dl className="eval-report-meta" aria-label="Report metadata">
          <div>
            <dt>Report</dt>
            <dd>{formatTutorBoardReportTime(report.createdAt) || "Unknown run"}</dd>
          </div>
          <div>
            <dt>Golden set</dt>
            <dd>{report.goldenPath}</dd>
          </div>
        </dl>
      </header>

      <section className="eval-summary-grid" aria-label="Evaluation summary">
        <article className="eval-summary-card">
          <span>Overall pass rate</span>
          <strong>{formatPassRate(report.passRate)}</strong>
          <p>
            {passedCount}/{report.cases.length} cases passed
          </p>
        </article>
        <article className="eval-summary-card">
          <span>Extractor model</span>
          <strong>{report.extractorModel ?? "n/a"}</strong>
          <p>{extractorCount} extractor-scored cases</p>
        </article>
        <article className="eval-summary-card">
          <span>Reference cases</span>
          <strong>{referenceCount}</strong>
          <p>Static utterance rubric checks</p>
        </article>
        <article className="eval-summary-card">
          <span>Failed cases</span>
          <strong>{report.failures.length}</strong>
          <p className={`eval-tone-${passTone(report.passRate)}`}>
            {report.failures.length === 0 ? "Clean run" : "See failure details below"}
          </p>
        </article>
      </section>

      <TutorBoardAxisSummaryPanel summaries={report.axisSummaries} />
      <TutorBoardCaseMatrix cases={report.cases} />
      <TutorBoardFailureList failures={report.failures} />
    </section>
  );
}
