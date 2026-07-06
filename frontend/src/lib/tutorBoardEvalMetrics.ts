import type {
  TutorBoardAxis,
  TutorBoardEvalReport,
  TutorBoardEvalTarget,
} from "../data/tutorBoardEval";
import { formatPercent, formatReportTime } from "./evalMetrics";

export const TUTOR_BOARD_AXIS_LABELS: Record<TutorBoardAxis, string> = {
  usage: "Usage",
  content: "Content",
  card_kind: "Card kind",
  grouping: "Grouping",
  reference: "Reference",
};

export const TUTOR_BOARD_AXIS_HINTS: Record<TutorBoardAxis, string> = {
  usage: "Should the extractor emit a card at all?",
  content: "Does the card payload carry the right detail?",
  card_kind: "Is text / plot / diagram / shape the right choice?",
  grouping: "Same line appends; new line creates a fresh card.",
  reference: "Does tutor speech point at the board appropriately?",
};

export function tutorBoardAxisLabel(axis: TutorBoardAxis): string {
  return TUTOR_BOARD_AXIS_LABELS[axis] ?? axis;
}

export function tutorBoardCaseLabel(caseId: string): string {
  return caseId.replace(/^tb-/, "");
}

export function summarizeActualItems(items: readonly Record<string, unknown>[]): string {
  if (items.length === 0) {
    return "—";
  }
  return items
    .map((item) => {
      const kind = typeof item.kind === "string" ? item.kind : "item";
      const id = typeof item.id === "string" ? item.id : "?";
      return `${kind}:${id}`;
    })
    .join(", ");
}

export function reportHeroSubtitle(report: TutorBoardEvalReport): string {
  const model = report.extractorModel ?? "reference-only";
  return `${report.cases.length} golden cases · extractor ${model}`;
}

export function formatTutorBoardReportTime(value: string): string {
  return formatReportTime(value);
}

export function formatPassRate(value: number): string {
  return formatPercent(value);
}

export function passTone(passRate: number): "good" | "neutral" | "warn" {
  if (passRate >= 0.9) return "good";
  if (passRate >= 0.7) return "neutral";
  return "warn";
}

export function tutorBoardTargetKey(target: TutorBoardEvalTarget): string {
  return target.catalogId;
}

export function tutorBoardTargetLabel(target: TutorBoardEvalTarget): string {
  return target.label || target.targetId;
}

export function tutorBoardTargetDetail(target: TutorBoardEvalTarget): string {
  const timeout = target.metadata.board_extractor_timeout_seconds;
  const model = target.extractorModel ?? target.metadata.board_extractor_model;
  const parts = [model, timeout !== undefined ? `${timeout}s timeout` : null].filter(Boolean);
  return parts.join(" · ") || target.sourceFileName;
}

export function axisPassRate(
  report: TutorBoardEvalReport,
  axis: TutorBoardAxis,
): number {
  const summary = report.axisSummaries.find((item) => item.axis === axis);
  return summary?.passRate ?? 0;
}

export function rankTutorBoardTargets(
  targets: readonly TutorBoardEvalTarget[],
): TutorBoardEvalTarget[] {
  return [...targets].sort((a, b) => {
    if (b.report.passRate !== a.report.passRate) {
      return b.report.passRate - a.report.passRate;
    }
    if (a.report.failures.length !== b.report.failures.length) {
      return a.report.failures.length - b.report.failures.length;
    }
    return a.comparisonLabel.localeCompare(b.comparisonLabel);
  });
}

export function casePassed(
  report: TutorBoardEvalReport,
  caseId: string,
): boolean | null {
  const match = report.cases.find((item) => item.caseId === caseId);
  return match ? match.passed : null;
}

export function caseActualItems(
  report: TutorBoardEvalReport,
  caseId: string,
): Record<string, unknown>[] {
  const match = report.cases.find((item) => item.caseId === caseId);
  return match ? match.actualItems : [];
}
