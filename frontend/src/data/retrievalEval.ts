export interface EvalMetrics {
  hitAt1: number;
  hitAt3: number;
  hitAt5: number;
  mrr: number;
  avgContentMatch: number;
  avgLatencyMs: number;
}

export interface EvalCaseResult {
  caseId: string;
  queryType: string;
  label: string;
  query: string;
  bestRank: number | null;
  reciprocalRank: number;
  hitAt1: boolean;
  hitAt3: boolean;
  hitAt5: boolean;
  contentMatchRatio: number;
}

export interface EvalTarget {
  targetId: string;
  label: string;
  comparisonAxis: string;
  metadata: Record<string, unknown>;
  provider: string;
  model: string;
  collectionName: string;
  caseCount: number;
  metrics: EvalMetrics;
  cases: EvalCaseResult[];
}

export interface EvalFailure {
  targetId: string;
  label: string;
  comparisonAxis: string;
  metadata: Record<string, unknown>;
  provider: string;
  model: string;
  error: string;
}

export interface RetrievalEvalReport {
  schemaVersion: number;
  comparisonAxis: string;
  createdAt: string;
  goldenPath: string;
  topK: number;
  targets: EvalTarget[];
  failures: EvalFailure[];
}

export interface RetrievalEvalReportTab {
  id: string;
  label: string;
  report: RetrievalEvalReport;
}

export { normalizeReport } from "../lib/evalNormalize";
export type { EvalCatalog, EvalReportSource, StructuredEvalTarget } from "../lib/evalCatalog";
export { loadEvalCatalog } from "../lib/evalCatalog";
