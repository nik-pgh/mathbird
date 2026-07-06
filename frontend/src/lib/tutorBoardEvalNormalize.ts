import type {
  TutorBoardAxis,
  TutorBoardAxisSummary,
  TutorBoardCaseFailure,
  TutorBoardCaseResult,
  TutorBoardEvalReport,
} from "../data/tutorBoardEval";

type RawRecord = Record<string, unknown>;

const AXES: TutorBoardAxis[] = [
  "usage",
  "content",
  "reference",
  "card_kind",
  "grouping",
];

function asRecord(value: unknown): RawRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as RawRecord)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asBool(value: unknown): boolean {
  return value === true;
}

function pick<T>(record: RawRecord, snakeKey: string, camelKey: string, fallback: T): unknown {
  return record[snakeKey] ?? record[camelKey] ?? fallback;
}

function asAxis(value: unknown): TutorBoardAxis {
  const axis = asString(value, "usage");
  return AXES.includes(axis as TutorBoardAxis) ? (axis as TutorBoardAxis) : "usage";
}

function asItemRecords(value: unknown): Record<string, unknown>[] {
  return asArray(value).map((item) => asRecord(item));
}

function normalizeAxisSummary(raw: unknown): TutorBoardAxisSummary {
  const item = asRecord(raw);
  return {
    axis: asAxis(item.axis),
    total: asNumber(item.total),
    passed: asNumber(item.passed),
    passRate: asNumber(pick(item, "pass_rate", "passRate", 0)),
  };
}

function normalizeCase(raw: unknown): TutorBoardCaseResult {
  const item = asRecord(raw);
  return {
    caseId: asString(pick(item, "case_id", "caseId", "")),
    axis: asAxis(item.axis),
    description: asString(item.description),
    passed: asBool(item.passed),
    failures: asArray(item.failures).map((entry) => asString(entry)),
    actualItems: asItemRecords(item.actual_items ?? item.actualItems),
    tutorUtterance: (() => {
      const value = item.tutor_utterance ?? item.tutorUtterance;
      return typeof value === "string" ? value : null;
    })(),
  };
}

function normalizeFailure(raw: unknown): TutorBoardCaseFailure {
  const item = asRecord(raw);
  return {
    caseId: asString(pick(item, "case_id", "caseId", "")),
    axis: asAxis(item.axis),
    description: asString(item.description),
    failures: asArray(item.failures).map((entry) => asString(entry)),
  };
}

export function normalizeTutorBoardReport(raw: unknown): TutorBoardEvalReport {
  const report = asRecord(raw);
  const extractorModel = report.extractor_model ?? report.extractorModel;
  return {
    schemaVersion: asNumber(pick(report, "schema_version", "schemaVersion", 1), 1),
    comparisonAxis: "tutor_board",
    createdAt: asString(pick(report, "created_at", "createdAt", "")),
    goldenPath: asString(pick(report, "golden_path", "goldenPath", "")),
    extractorModel: typeof extractorModel === "string" ? extractorModel : null,
    passRate: asNumber(pick(report, "pass_rate", "passRate", 0)),
    axisSummaries: asArray(report.axis_summaries ?? report.axisSummaries).map(
      normalizeAxisSummary,
    ),
    cases: asArray(report.cases).map(normalizeCase),
    failures: asArray(report.failures).map(normalizeFailure),
  };
}
