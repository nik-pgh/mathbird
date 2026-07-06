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
  createdAt: string;
  goldenPath: string;
  extractorModel: string | null;
  passRate: number;
  axisSummaries: TutorBoardAxisSummary[];
  cases: TutorBoardCaseResult[];
  failures: TutorBoardCaseFailure[];
}

export { normalizeTutorBoardReport } from "../lib/tutorBoardEvalNormalize";
