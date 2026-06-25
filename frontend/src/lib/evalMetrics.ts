import { EvalCaseResult, EvalTarget, RetrievalEvalReport } from "../data/retrievalEval";

export type MetricKey =
  | "hitAt1"
  | "hitAt3"
  | "hitAt5"
  | "mrr"
  | "avgContentMatch";

export interface CaseSummary {
  caseId: string;
  queryType: string;
  label: string;
  results: Array<{
    targetKey: string;
    bestRank: number | null;
    hitAt1: boolean;
    hitAt3: boolean;
    contentMatchRatio: number;
  }>;
}

export function targetKey(target: Pick<EvalTarget, "targetId" | "provider" | "model">): string {
  return target.targetId || `${target.provider}/${target.model}`;
}

export function targetLabel(target: Pick<EvalTarget, "label" | "model">): string {
  return target.label || target.model;
}

export function targetDetail(target: Pick<EvalTarget, "provider" | "model">): string {
  return `${target.provider} / ${target.model}`;
}

export function comparisonTitle(axis: string): string {
  if (axis === "chunk_policy") return "Chunking policy comparison";
  if (axis === "embedding_model") return "Embedding model comparison";
  if (axis === "structured_lookup") return "Structured lookup comparison";
  return "Retrieval target comparison";
}

export function goldenSetSummary(axis: string): string {
  if (axis === "structured_lookup") {
    return "Page, section, figure, equation, and example lookups";
  }
  return "Definitions, formulas, figures, concepts, student-style prompts";
}

export function failureSummary(axis: string): string {
  if (axis === "structured_lookup") {
    return "Missing collection or failed retrieval path";
  }
  return "Missing or unavailable embedding collections";
}

export function rankTargets(targets: readonly EvalTarget[]): EvalTarget[] {
  return [...targets].sort((a, b) => {
    const hitAt3 = b.metrics.hitAt3 - a.metrics.hitAt3;
    if (hitAt3 !== 0) return hitAt3;

    const mrr = b.metrics.mrr - a.metrics.mrr;
    if (mrr !== 0) return mrr;

    const hitAt5 = b.metrics.hitAt5 - a.metrics.hitAt5;
    if (hitAt5 !== 0) return hitAt5;

    return a.metrics.avgLatencyMs - b.metrics.avgLatencyMs;
  });
}

export function caseSummaries(
  report: RetrievalEvalReport,
  targets: readonly EvalTarget[] = report.targets,
): CaseSummary[] {
  const baseTarget = report.targets[0];
  if (!baseTarget) return [];

  const resultsByTarget = new Map(
    targets.map((target) => [
      targetKey(target),
      new Map(target.cases.map((item) => [item.caseId, item])),
    ]),
  );

  return baseTarget.cases.map((baseCase) => ({
    caseId: baseCase.caseId,
    queryType: baseCase.queryType,
    label: baseCase.label,
    results: targets.map((target) => {
      const key = targetKey(target);
      const result: EvalCaseResult | undefined = resultsByTarget
        .get(key)
        ?.get(baseCase.caseId);
      return {
        targetKey: key,
        bestRank: result?.bestRank ?? null,
        hitAt1: result?.hitAt1 ?? false,
        hitAt3: result?.hitAt3 ?? false,
        contentMatchRatio: result?.contentMatchRatio ?? 0,
      };
    }),
  }));
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatScore(value: number): string {
  return value.toFixed(3);
}

export function formatLatency(value: number): string {
  return `${Math.round(value)} ms`;
}

export function formatReportTime(value: string): string {
  const match = value.match(
    /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/,
  );
  if (!match) return value;

  const [, year, month, day, hour, minute, second] = match;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(
    new Date(
      Date.UTC(
        Number(year),
        Number(month) - 1,
        Number(day),
        Number(hour),
        Number(minute),
        Number(second),
      ),
    ),
  );
}
