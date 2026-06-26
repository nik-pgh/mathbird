import type { ProgressSummary, SessionProgressUpdate } from "./progress";
import type { Syllabus, SyllabusChapter, SyllabusProblem } from "./syllabus";

export type ProblemStatus = "not_started" | "in_progress" | "mastered";

export interface RoadmapProblemView {
  id: string;
  label: string;
  bookPageNumber: number;
  status: ProblemStatus;
  isFocus: boolean;
  isNext: boolean;
}

export interface RoadmapConceptView {
  id: string;
  title: string;
  problems: RoadmapProblemView[];
  masteredCount: number;
  totalCount: number;
}

export interface RoadmapChapterView {
  id: string;
  title: string;
  shortLabel: string;
  concepts: RoadmapConceptView[];
  problems: RoadmapProblemView[];
  masteredCount: number;
  totalCount: number;
  isFocusedChapter: boolean;
  hasInProgress: boolean;
}

export interface RoadmapFocus {
  chapterTitle: string;
  conceptTitle: string;
  problemLabel: string;
  bookPageNumber: number;
}

export interface RoadmapNext {
  chapterTitle: string;
  conceptTitle: string;
  problemLabel: string;
  bookPageNumber: number;
}

export interface RoadmapViewModel {
  chapters: RoadmapChapterView[];
  summary: ProgressSummary;
  focus: RoadmapFocus | null;
  next: RoadmapNext | null;
  ariaLabel: string;
  statusCaption: string | null;
}

function chapterShortLabel(chapter: SyllabusChapter): string {
  if (chapter.number != null) {
    return `Ch ${chapter.number}`;
  }
  const title = chapter.title.trim();
  return title.length > 14 ? `${title.slice(0, 12)}…` : title;
}

/** Prefer the printed textbook page; omit PDF page indices in the UI. */
export function bookPageNumber(problem: SyllabusProblem): number {
  const printed = problem.printed_page_number ?? 0;
  return printed > 0 ? printed : 0;
}

export function formatBookPageLabel(bookPageNumber: number): string | null {
  return bookPageNumber > 0 ? `p. ${bookPageNumber}` : null;
}

function problemCaption(label: string, bookPageNumber: number): string {
  const page = formatBookPageLabel(bookPageNumber);
  return page ? `${label} · ${page}` : label;
}

function buildAriaLabel(focus: RoadmapFocus | null, summary: ProgressSummary): string {
  const progress = `${summary.mastered} of ${summary.total} problems mastered`;
  if (focus === null) {
    return `Textbook roadmap. ${progress}.`;
  }
  const page = formatBookPageLabel(focus.bookPageNumber);
  const pageSuffix = page ? `, ${page}` : "";
  return (
    `Textbook roadmap. ${progress}. ` +
    `Current focus: ${focus.chapterTitle}, ${focus.conceptTitle}, ${focus.problemLabel}${pageSuffix}.`
  );
}

function buildStatusCaption(
  focus: RoadmapFocus | null,
  next: RoadmapNext | null,
  summary: ProgressSummary,
): string | null {
  if (focus !== null) {
    return problemCaption(focus.problemLabel, focus.bookPageNumber);
  }
  if (next !== null) {
    return `Next: ${problemCaption(next.problemLabel, next.bookPageNumber)}`;
  }
  if (summary.total <= 0) {
    return null;
  }
  if (summary.mastered >= summary.total) {
    return "All problems mastered";
  }
  return "Not started yet";
}

function findProblemContext(
  syllabus: Syllabus,
  problemId: string,
): RoadmapNext | null {
  for (const chapter of syllabus.chapters) {
    for (const concept of chapter.concepts) {
      for (const problem of concept.problems) {
        if (problem.id === problemId) {
          return {
            chapterTitle: chapter.title,
            conceptTitle: concept.title,
            problemLabel: problem.label,
            bookPageNumber: bookPageNumber(problem),
          };
        }
      }
    }
  }
  return null;
}

/** Merge a static syllabus with a live progress snapshot for rendering. */
export function buildRoadmapViewModel(
  syllabus: Syllabus | null,
  snapshot: SessionProgressUpdate | null,
): RoadmapViewModel | null {
  if (!syllabus || syllabus.chapters.length === 0) {
    return null;
  }

  const statusById = new Map<string, ProblemStatus>();
  for (const node of snapshot?.nodes ?? []) {
    statusById.set(node.problem_id, node.status);
  }

  const focusId = snapshot?.focus?.problem_id ?? null;
  const nextId = snapshot?.next_suggestion?.problem_id ?? null;

  let totalProblems = 0;
  let masteredCount = 0;
  let inProgressCount = 0;
  let focusInfo: RoadmapFocus | null = null;
  let nextInfo: RoadmapNext | null = null;

  const chapters: RoadmapChapterView[] = [];

  for (const chapter of syllabus.chapters) {
    const chapterProblems: RoadmapProblemView[] = [];
    const concepts: RoadmapConceptView[] = [];

    for (const concept of chapter.concepts) {
      const conceptProblems: RoadmapProblemView[] = [];

      for (const problem of concept.problems) {
        const status = statusById.get(problem.id) ?? "not_started";
        const isFocus = problem.id === focusId;
        const isNext = problem.id === nextId;
        const page = bookPageNumber(problem);

        if (status === "mastered") {
          masteredCount += 1;
        } else if (status === "in_progress") {
          inProgressCount += 1;
        }
        totalProblems += 1;

        if (isFocus) {
          focusInfo = {
            chapterTitle: chapter.title,
            conceptTitle: concept.title,
            problemLabel: problem.label,
            bookPageNumber: page,
          };
        }

        if (isNext) {
          nextInfo = {
            chapterTitle: chapter.title,
            conceptTitle: concept.title,
            problemLabel: problem.label,
            bookPageNumber: page,
          };
        }

        const problemView: RoadmapProblemView = {
          id: problem.id,
          label: problem.label,
          bookPageNumber: page,
          status,
          isFocus,
          isNext,
        };

        conceptProblems.push(problemView);
        chapterProblems.push(problemView);
      }

      concepts.push({
        id: concept.id,
        title: concept.title,
        problems: conceptProblems,
        masteredCount: conceptProblems.filter((problem) => problem.status === "mastered").length,
        totalCount: conceptProblems.length,
      });
    }

    const isFocusedChapter = chapterProblems.some((problem) => problem.isFocus);

    chapters.push({
      id: chapter.id,
      title: chapter.title,
      shortLabel: chapterShortLabel(chapter),
      concepts,
      problems: chapterProblems,
      masteredCount: chapterProblems.filter((problem) => problem.status === "mastered").length,
      totalCount: chapterProblems.length,
      isFocusedChapter,
      hasInProgress: chapterProblems.some((problem) => problem.status === "in_progress"),
    });
  }

  if (chapters.length === 0) {
    return null;
  }

  if (nextInfo === null && nextId !== null) {
    nextInfo = findProblemContext(syllabus, nextId);
  }

  const summary = snapshot?.summary ?? {
    mastered: masteredCount,
    in_progress: inProgressCount,
    total: totalProblems,
  };

  return {
    chapters,
    summary,
    focus: focusInfo,
    next: nextInfo,
    ariaLabel: buildAriaLabel(focusInfo, summary),
    statusCaption: buildStatusCaption(focusInfo, nextInfo, summary),
  };
}

/** Mastery fill within a chapter segment (0–100). */
export function chapterMasteryPercent(masteredCount: number, totalCount: number): number {
  if (totalCount <= 0) {
    return 0;
  }
  return (masteredCount / totalCount) * 100;
}
