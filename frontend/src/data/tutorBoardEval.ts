export type TutorBoardAxis =
  | "usage"
  | "content"
  | "reference"
  | "card_kind"
  | "grouping";

export interface TutorBoardAxisSummary {
  axis: TutorBoardAxis;
  total: number;
  passed: number;
  passRate: number;
}

export interface TutorBoardCaseResult {
  caseId: string;
  axis: TutorBoardAxis;
  description: string;
  passed: boolean;
  failures: string[];
  actualItems: Record<string, unknown>[];
  tutorUtterance: string | null;
}

export interface TutorBoardCaseFailure {
  caseId: string;
  axis: TutorBoardAxis;
  description: string;
  failures: string[];
}

export interface TutorBoardEvalReport {
  schemaVersion: number;
  comparisonAxis: "tutor_board";
  targetId: string;
  label: string;
  metadata: Record<string, unknown>;
  createdAt: string;
  goldenPath: string;
  extractorModel: string | null;
  passRate: number;
  axisSummaries: TutorBoardAxisSummary[];
  cases: TutorBoardCaseResult[];
  failures: TutorBoardCaseFailure[];
}

export interface TutorBoardEvalSource {
  id: string;
  fileName: string;
  report: TutorBoardEvalReport;
}

export interface TutorBoardEvalTarget {
  catalogId: string;
  sourceId: string;
  sourceFileName: string;
  targetId: string;
  label: string;
  reportCreatedAt: string;
  goldenPath: string;
  extractorModel: string | null;
  metadata: Record<string, unknown>;
  report: TutorBoardEvalReport;
  comparisonLabel: string;
  pickerPrimary: string;
  pickerSecondary: string;
  pickerTitle: string;
}

export { normalizeTutorBoardReport } from "../lib/tutorBoardEvalNormalize";
