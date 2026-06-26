import { ChevronDown } from "lucide-react";
import { useMemo, useState, type WheelEvent } from "react";
import { CANVAS_WHEEL_IGNORE_ATTR } from "../../lib/canvasViewport";
import {
  buildRoadmapViewModel,
  chapterMasteryPercent,
  formatBookPageLabel,
  type ProblemStatus,
  type RoadmapChapterView,
  type RoadmapConceptView,
  type RoadmapProblemView,
} from "../../lib/roadmapProgress";
import type { Syllabus } from "../../lib/syllabus";
import { useProgressSnapshot } from "./ProgressSnapshotContext";
import "../../styles/roadmap-progress.css";

function stopBoardWheel(event: WheelEvent<HTMLElement>) {
  event.stopPropagation();
}

interface Props {
  syllabus: Syllabus;
}

const STATUS_LABEL: Record<ProblemStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  mastered: "Mastered",
};

export default function RoadmapProgressPanel({ syllabus }: Props) {
  const snapshot = useProgressSnapshot();
  const [expanded, setExpanded] = useState(true);

  const viewModel = useMemo(
    () => buildRoadmapViewModel(syllabus, snapshot),
    [syllabus, snapshot],
  );

  if (viewModel === null) {
    return null;
  }

  const { chapters, summary, statusCaption, ariaLabel } = viewModel;
  const chapterCount = chapters.length;
  const chaptersWithProblems = chapters.filter((chapter) => chapter.totalCount > 0).length;
  const conceptCount = chapters.reduce((count, chapter) => count + chapter.concepts.length, 0);

  return (
    <aside
      {...{ [CANVAS_WHEEL_IGNORE_ATTR]: "" }}
      className={`roadmap-progress-panel${expanded ? " roadmap-progress-panel--expanded" : ""}`}
      aria-label={ariaLabel}
      onWheel={stopBoardWheel}
    >
      <button
        type="button"
        className="roadmap-progress-header"
        aria-expanded={expanded}
        aria-controls="roadmap-progress-detail"
        onClick={() => setExpanded((value) => !value)}
      >
        <span className="roadmap-progress-title">Roadmap</span>
        <span className="roadmap-progress-header-meta">
          <span className="roadmap-progress-count">
            {summary.mastered}/{summary.total}
          </span>
          <ChevronDown
            size={14}
            className={`roadmap-progress-chevron${expanded ? " roadmap-progress-chevron--open" : ""}`}
            aria-hidden="true"
          />
        </span>
      </button>

      {summary.total > 0 && (
        <p className="roadmap-progress-note">
          {summary.total} problem{summary.total === 1 ? "" : "s"} · {chapterCount} chapter
          {chapterCount === 1 ? "" : "s"} · {conceptCount} section{conceptCount === 1 ? "" : "s"}
          {chaptersWithProblems < chapterCount
            ? ` (${chaptersWithProblems} with exercises)`
            : ""}
        </p>
      )}

      <div
        className="roadmap-progress-chapters"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={Math.max(summary.total, 1)}
        aria-valuenow={summary.mastered}
        aria-label={ariaLabel}
        onWheel={stopBoardWheel}
      >
        {chapters.map((chapter) => (
          <ChapterBar key={chapter.id} chapter={chapter} />
        ))}
      </div>

      {statusCaption !== null && (
        <p className="roadmap-progress-status-label">{statusCaption}</p>
      )}

      {expanded && (
        <div
          id="roadmap-progress-detail"
          className="roadmap-progress-detail"
          onWheel={stopBoardWheel}
        >
          {chapters.map((chapter) => (
            <ChapterDetail key={chapter.id} chapter={chapter} />
          ))}
        </div>
      )}
    </aside>
  );
}

function ChapterBar({ chapter }: { chapter: RoadmapChapterView }) {
  const hasProblems = chapter.totalCount > 0;
  const masteryPct = chapterMasteryPercent(chapter.masteredCount, chapter.totalCount);

  return (
    <div
      className={`roadmap-progress-row${
        chapter.isFocusedChapter ? " roadmap-progress-row--focus" : ""
      }${chapter.hasInProgress ? " roadmap-progress-row--working" : ""}${
        !hasProblems ? " roadmap-progress-row--empty" : ""
      }`}
      title={chapter.title}
    >
      <div
        className={`roadmap-progress-bar${!hasProblems ? " roadmap-progress-bar--empty" : ""}`}
      >
        {hasProblems && (
          <>
            <div
              className="roadmap-progress-bar-mastered"
              style={{ width: `${masteryPct}%` }}
            />
            {chapter.hasInProgress && <div className="roadmap-progress-bar-active" />}
          </>
        )}
      </div>
      <span className="roadmap-progress-chapter-label">
        {chapter.shortLabel}
        {hasProblems ? ` · ${chapter.totalCount}` : ""}
      </span>
    </div>
  );
}

function ChapterDetail({ chapter }: { chapter: RoadmapChapterView }) {
  const hasProblems = chapter.totalCount > 0;

  return (
    <section
      className={`roadmap-detail-chapter${
        chapter.isFocusedChapter ? " roadmap-detail-chapter--focus" : ""
      }`}
    >
      <header className="roadmap-detail-chapter-head">
        <h3 className="roadmap-detail-chapter-title">{chapter.title}</h3>
        <span className="roadmap-detail-chapter-count">
          {hasProblems ? `${chapter.masteredCount}/${chapter.totalCount}` : "—"}
        </span>
      </header>

      {chapter.concepts.map((concept) => (
        <ConceptDetail key={concept.id} concept={concept} />
      ))}
    </section>
  );
}

function ConceptDetail({ concept }: { concept: RoadmapConceptView }) {
  return (
    <div className="roadmap-detail-concept">
      <p className="roadmap-detail-concept-title">{concept.title}</p>
      {concept.problems.length > 0 && (
        <ul className="roadmap-detail-problems">
          {concept.problems.map((problem) => (
            <ProblemRow key={problem.id} problem={problem} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ProblemRow({ problem }: { problem: RoadmapProblemView }) {
  const pageLabel = formatBookPageLabel(problem.bookPageNumber);

  return (
    <li
      className={`roadmap-detail-problem roadmap-detail-problem--${problem.status}${
        problem.isFocus ? " roadmap-detail-problem--focus" : ""
      }${problem.isNext ? " roadmap-detail-problem--next" : ""}`}
    >
      <div className="roadmap-detail-problem-main">
        <span className="roadmap-detail-problem-label">{problem.label}</span>
        <span className="roadmap-detail-problem-meta">
          {pageLabel !== null && (
            <span className="roadmap-detail-problem-page">{pageLabel}</span>
          )}
          <span className="roadmap-detail-problem-status">{STATUS_LABEL[problem.status]}</span>
          {problem.isFocus && <span className="roadmap-detail-badge">Focus</span>}
          {problem.isNext && !problem.isFocus && (
            <span className="roadmap-detail-badge roadmap-detail-badge--next">Next</span>
          )}
        </span>
      </div>
    </li>
  );
}
