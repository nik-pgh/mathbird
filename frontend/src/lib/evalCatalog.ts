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

const embeddingEvalModules = import.meta.glob("../data/embeddingEval*.json");
const chunkingEvalModules = import.meta.glob("../data/chunkingEval*.json");
const structuredEvalModules = import.meta.glob("../data/structuredEval*.json");

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

export interface EvalCatalog {
  structuredEvalSources: EvalReportSource[];
  structuredEvalCatalog: StructuredEvalTarget[];
  retrievalEvalReports: RetrievalEvalReportTab[];
}

function sourceIdFromPath(path: string): string {
  return path.replace("../data/", "").replace(/\.json$/, "");
}

async function loadJsonModules(
  modules: Record<string, () => Promise<unknown>>,
): Promise<Record<string, unknown>> {
  const entries = await Promise.all(
    Object.entries(modules).map(async ([path, loader]) => {
      const mod = (await loader()) as { default: unknown };
      return [path, mod.default] as const;
    }),
  );
  return Object.fromEntries(entries);
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
  sources: readonly EvalReportSource[],
): RetrievalEvalReport | null {
  if (selected.length === 0) {
    return null;
  }

  const first = selected[0];
  const source = sources.find((item) => item.id === first.sourceId);
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
      targetId: item.catalogId,
      label: item.shortLabel,
    })),
    failures: [],
  };
}

function buildAxisTabs(
  embeddingModules: Record<string, unknown>,
  chunkingModules: Record<string, unknown>,
  structuredModules: Record<string, unknown>,
  structuredEvalCatalog: StructuredEvalTarget[],
  structuredEvalSources: EvalReportSource[],
): RetrievalEvalReportTab[] {
  const tabs: RetrievalEvalReportTab[] = [];

  const embeddingReport = latestReport(embeddingModules);
  if (embeddingReport) {
    tabs.push({
      id: AXIS_TAB_META.embedding_model.id,
      label: AXIS_TAB_META.embedding_model.label,
      report: embeddingReport,
    });
  }

  const chunkingReport = latestReport(chunkingModules);
  if (chunkingReport) {
    tabs.push({
      id: AXIS_TAB_META.chunk_policy.id,
      label: AXIS_TAB_META.chunk_policy.label,
      report: chunkingReport,
    });
  }

  const structuredReport =
    buildStructuredComparisonReport(
      defaultStructuredSelection(structuredEvalCatalog),
      structuredEvalSources,
    ) ?? latestReport(structuredModules);
  if (structuredReport) {
    tabs.push({
      id: AXIS_TAB_META.structured_lookup.id,
      label: AXIS_TAB_META.structured_lookup.label,
      report: structuredReport,
    });
  }

  return tabs;
}

export async function loadEvalCatalog(): Promise<EvalCatalog> {
  const [embeddingModules, chunkingModules, structuredModules] = await Promise.all([
    loadJsonModules(embeddingEvalModules),
    loadJsonModules(chunkingEvalModules),
    loadJsonModules(structuredEvalModules),
  ]);

  const structuredEvalSources = buildSources(structuredModules);
  const structuredEvalCatalog = buildStructuredEvalCatalog(structuredEvalSources);
  const retrievalEvalReports = buildAxisTabs(
    embeddingModules,
    chunkingModules,
    structuredModules,
    structuredEvalCatalog,
    structuredEvalSources,
  );

  return {
    structuredEvalSources,
    structuredEvalCatalog,
    retrievalEvalReports,
  };
}
