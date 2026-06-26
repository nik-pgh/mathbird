import type {
  EvalTarget,
  RetrievalEvalReport,
  RetrievalEvalReportTab,
} from "../data/retrievalEval";
import { normalizeReport } from "./evalNormalize";

const CHUNK_POLICIES = [
  "page_section_window_512",
  "block_neighbor_1",
  "math_object_window",
  "block",
] as const;

const AXIS_TAB_META: Record<string, { id: string; label: string }> = {
  embedding_model: { id: "embedding", label: "Embedding Experiments" },
  chunk_policy: { id: "chunking", label: "Chunking Experiments" },
  structured_lookup: { id: "structured", label: "Structured Lookup" },
};

const embeddingEvalModules = import.meta.glob("../data/embeddingEval*.json", {
  eager: true,
  import: "default",
}) as Record<string, unknown>;

const chunkingEvalModules = import.meta.glob("../data/chunkingEval*.json", {
  eager: true,
  import: "default",
}) as Record<string, unknown>;

const structuredEvalModules = import.meta.glob("../data/structuredEval*.json", {
  eager: true,
  import: "default",
}) as Record<string, unknown>;

export interface EvalReportSource {
  id: string;
  fileName: string;
  report: RetrievalEvalReport;
}

export interface StructuredEvalTarget {
  catalogId: string;
  sourceId: string;
  reportCreatedAt: string;
  goldenPath: string;
  target: EvalTarget;
  facets: {
    chunkPolicy: string | null;
    retrievalPath: string | null;
    embedding: string;
  };
  shortLabel: string;
}

function sourceIdFromPath(path: string): string {
  return path.replace("../data/", "").replace(/\.json$/, "");
}

function buildSources(modules: Record<string, unknown>): EvalReportSource[] {
  return Object.entries(modules)
    .map(([path, raw]) => ({
      id: sourceIdFromPath(path),
      fileName: `${sourceIdFromPath(path)}.json`,
      report: normalizeReport(raw),
    }))
    .sort((a, b) => b.report.createdAt.localeCompare(a.report.createdAt));
}

function latestReport(modules: Record<string, unknown>): RetrievalEvalReport | null {
  return buildSources(modules)[0]?.report ?? null;
}

export function extractChunkPolicy(collectionName: string): string | null {
  if (!collectionName.startsWith("mathbird_chunk_")) {
    return null;
  }
  const rest = collectionName.slice("mathbird_chunk_".length);
  for (const policy of CHUNK_POLICIES) {
    if (rest.startsWith(`${policy}_`)) {
      return policy;
    }
  }
  return null;
}

function retrievalPathFromTarget(target: EvalTarget): string | null {
  const path = target.metadata.path;
  return typeof path === "string" ? path : null;
}

function buildShortLabel(
  target: EvalTarget,
  facets: StructuredEvalTarget["facets"],
): string {
  const parts: string[] = [];
  if (facets.chunkPolicy) {
    parts.push(facets.chunkPolicy);
  }
  if (facets.retrievalPath) {
    parts.push(facets.retrievalPath);
  } else if (target.label && target.label !== target.model) {
    parts.push(target.label);
  }
  return parts.join(" · ");
}

export function buildStructuredEvalCatalog(
  sources: readonly EvalReportSource[],
): StructuredEvalTarget[] {
  const catalog: StructuredEvalTarget[] = [];

  for (const source of sources) {
    for (const target of source.report.targets) {
      const chunkPolicy = extractChunkPolicy(target.collectionName);
      const retrievalPath = retrievalPathFromTarget(target);
      const facets = {
        chunkPolicy,
        retrievalPath,
        embedding: `${target.provider}/${target.model}`,
      };
      catalog.push({
        catalogId: `${source.id}::${target.targetId}`,
        sourceId: source.id,
        reportCreatedAt: source.report.createdAt,
        goldenPath: source.report.goldenPath,
        target,
        facets,
        shortLabel: buildShortLabel(target, facets),
      });
    }
  }

  return catalog.sort((a, b) => a.shortLabel.localeCompare(b.shortLabel));
}

export function defaultStructuredSelection(
  catalog: readonly StructuredEvalTarget[],
): StructuredEvalTarget[] {
  const production = catalog.filter((item) => item.facets.retrievalPath === "production");
  if (production.length === 0) {
    const newestSource = catalog[0]?.sourceId;
    return catalog.filter((item) => item.sourceId === newestSource);
  }

  const byCollection = new Map<string, StructuredEvalTarget>();
  for (const item of production) {
    const key = item.target.collectionName;
    const existing = byCollection.get(key);
    if (!existing || item.reportCreatedAt > existing.reportCreatedAt) {
      byCollection.set(key, item);
    }
  }
  return [...byCollection.values()].sort((a, b) =>
    a.shortLabel.localeCompare(b.shortLabel),
  );
}

export function buildStructuredComparisonReport(
  selected: readonly StructuredEvalTarget[],
): RetrievalEvalReport | null {
  if (selected.length === 0) {
    return null;
  }

  const first = selected[0];
  const source = structuredEvalSources.find((item) => item.id === first.sourceId);
  if (!source) {
    return null;
  }

  return {
    schemaVersion: source.report.schemaVersion,
    comparisonAxis: "structured_lookup",
    createdAt: selected.map((item) => item.reportCreatedAt).sort().slice(-1)[0] ?? "",
    goldenPath: first.goldenPath,
    topK: source.report.topK,
    targets: selected.map((item) => ({
      ...item.target,
      label: item.shortLabel,
    })),
    failures: [],
  };
}

function buildAxisTabs(): RetrievalEvalReportTab[] {
  const tabs: RetrievalEvalReportTab[] = [];

  const embeddingReport = latestReport(embeddingEvalModules);
  if (embeddingReport) {
    tabs.push({
      id: AXIS_TAB_META.embedding_model.id,
      label: AXIS_TAB_META.embedding_model.label,
      report: embeddingReport,
    });
  }

  const chunkingReport = latestReport(chunkingEvalModules);
  if (chunkingReport) {
    tabs.push({
      id: AXIS_TAB_META.chunk_policy.id,
      label: AXIS_TAB_META.chunk_policy.label,
      report: chunkingReport,
    });
  }

  const structuredReport =
    buildStructuredComparisonReport(defaultStructuredSelection(structuredEvalCatalog)) ??
    latestReport(structuredEvalModules);
  if (structuredReport) {
    tabs.push({
      id: AXIS_TAB_META.structured_lookup.id,
      label: AXIS_TAB_META.structured_lookup.label,
      report: structuredReport,
    });
  }

  return tabs;
}

export const structuredEvalSources = buildSources(structuredEvalModules);
export const structuredEvalCatalog = buildStructuredEvalCatalog(structuredEvalSources);
export const retrievalEvalReports = buildAxisTabs();
export const retrievalEvalReport = retrievalEvalReports[0]?.report;
