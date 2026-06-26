import {
  EvalCaseResult,
  EvalFailure,
  EvalMetrics,
  EvalTarget,
  RetrievalEvalReport,
} from "../data/retrievalEval";

type RawRecord = Record<string, unknown>;

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

function asNullableRank(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pick<T>(record: RawRecord, snakeKey: string, camelKey: string, fallback: T): unknown {
  return record[snakeKey] ?? record[camelKey] ?? fallback;
}

function normalizeMetrics(raw: unknown): EvalMetrics {
  const metrics = asRecord(raw);
  return {
    hitAt1: asNumber(pick(metrics, "hit_at_1", "hitAt1", 0)),
    hitAt3: asNumber(pick(metrics, "hit_at_3", "hitAt3", 0)),
    hitAt5: asNumber(pick(metrics, "hit_at_5", "hitAt5", 0)),
    mrr: asNumber(metrics.mrr),
    avgContentMatch: asNumber(
      pick(metrics, "avg_content_match", "avgContentMatch", 0),
    ),
    avgLatencyMs: asNumber(pick(metrics, "avg_latency_ms", "avgLatencyMs", 0)),
  };
}

function fallbackCaseLabel(caseId: string, query: string): string {
  if (query) return query;
  return caseId || "Untitled case";
}

function normalizeCase(raw: unknown): EvalCaseResult {
  const item = asRecord(raw);
  const caseId = asString(pick(item, "case_id", "caseId", ""));
  const query = asString(item.query);
  return {
    caseId,
    queryType: asString(pick(item, "query_type", "queryType", "unknown"), "unknown"),
    label: asString(item.label, fallbackCaseLabel(caseId, query)),
    query,
    bestRank: asNullableRank(pick(item, "best_rank", "bestRank", null)),
    reciprocalRank: asNumber(pick(item, "reciprocal_rank", "reciprocalRank", 0)),
    hitAt1: asBool(pick(item, "hit_at_1", "hitAt1", false)),
    hitAt3: asBool(pick(item, "hit_at_3", "hitAt3", false)),
    hitAt5: asBool(pick(item, "hit_at_5", "hitAt5", false)),
    contentMatchRatio: asNumber(
      pick(item, "content_match_ratio", "contentMatchRatio", 0),
    ),
  };
}

function normalizeTarget(raw: unknown): EvalTarget {
  const target = asRecord(raw);
  const provider = asString(target.provider);
  const model = asString(target.model);
  const label = asString(target.label, model || provider || "Target");
  return {
    targetId: asString(
      pick(target, "target_id", "targetId", ""),
      `${provider}:${model}`,
    ),
    label,
    comparisonAxis: asString(
      pick(target, "comparison_axis", "comparisonAxis", "embedding_model"),
      "embedding_model",
    ),
    metadata: asRecord(target.metadata),
    provider,
    model,
    collectionName: asString(pick(target, "collection_name", "collectionName", "")),
    caseCount: asNumber(pick(target, "case_count", "caseCount", 0)),
    metrics: normalizeMetrics(target.metrics),
    cases: asArray(target.cases).map(normalizeCase),
  };
}

function normalizeFailure(raw: unknown): EvalFailure {
  const failure = asRecord(raw);
  const provider = asString(failure.provider);
  const model = asString(failure.model);
  return {
    targetId: asString(
      pick(failure, "target_id", "targetId", ""),
      `${provider}:${model}`,
    ),
    label: asString(failure.label, model || provider || "Target"),
    comparisonAxis: asString(
      pick(failure, "comparison_axis", "comparisonAxis", "embedding_model"),
      "embedding_model",
    ),
    metadata: asRecord(failure.metadata),
    provider,
    model,
    error: asString(failure.error),
  };
}

export function normalizeReport(raw: unknown): RetrievalEvalReport {
  const report = asRecord(raw);
  return {
    schemaVersion: asNumber(pick(report, "schema_version", "schemaVersion", 1), 1),
    comparisonAxis: asString(
      pick(report, "comparison_axis", "comparisonAxis", "embedding_model"),
      "embedding_model",
    ),
    createdAt: asString(pick(report, "created_at", "createdAt", "")),
    goldenPath: asString(pick(report, "golden_path", "goldenPath", "")),
    topK: asNumber(pick(report, "top_k", "topK", 0)),
    targets: asArray(report.targets).map(normalizeTarget),
    failures: asArray(report.failures).map(normalizeFailure),
  };
}
