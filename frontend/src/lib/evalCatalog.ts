import type {
  EvalTarget,
  RetrievalEvalReport,
  RetrievalEvalReportTab,
} from "../data/retrievalEval";
import type { TutorBoardEvalReport } from "../data/tutorBoardEval";
import { normalizeReport } from "./evalNormalize";
import { normalizeTutorBoardReport } from "./tutorBoardEvalNormalize";

const CHUNK_POLICIES = [
  "math_object_window_page_anchor",
  "page_section_window_512",
  "block_neighbor_1",
  "math_object_window",
  "block",
] as const;

const CHUNK_POLICY_LABELS: Record<string, string> = {
  block: "Block",
  block_neighbor_1: "Block + neighbors",
  page_section_window_512: "Page-section window",
  math_object_window: "Math object window",
  math_object_window_page_anchor: "Math object window + page anchors",
};

const RETRIEVAL_PATH_LABELS: Record<string, string> = {
  production: "Production retrieve()",
  structured_only: "Structured lookup only",
  semantic_only: "Semantic search only",
};

const AXIS_TAB_META: Record<string, { id: string; label: string }> = {
  embedding_model: { id: "embedding", label: "Embedding Experiments" },
  chunk_policy: { id: "chunking", label: "Chunking Experiments" },
  structured_lookup: { id: "structured", label: "Structured Lookup" },
};

const embeddingEvalModules = import.meta.glob("../data/embeddingEval*.json");
const chunkingEvalModules = import.meta.glob("../data/chunkingEval*.json");
const structuredEvalModules = import.meta.glob("../data/structuredEval*.json");
const tutorBoardEvalModules = import.meta.glob("../data/tutorBoardEval*.json");

export interface EvalReportSource {
  id: string;
  fileName: string;
  report: RetrievalEvalReport;
}

export interface StructuredEvalTarget {
  catalogId: string;
  sourceId: string;
  sourceFileName: string;
  reportCreatedAt: string;
  goldenPath: string;
  target: EvalTarget;
  facets: {
    chunkPolicy: string | null;
    retrievalPath: string | null;
    embedding: string;
  };
  /** Full single-line label for tables and screen readers. */
  comparisonLabel: string;
  /** Primary line for compact picker chips (chunk policy). */
  pickerPrimary: string;
  /** Secondary line for picker chips (embedding + retrieval path). */
  pickerSecondary: string;
  /** Tooltip with collection, source file, and run time. */
  pickerTitle: string;
}

export interface StructuredEvalPolicyGroup {
  sourceId: string;
  sourceFileName: string;
  reportCreatedAt: string;
  goldenPath: string;
  chunkPolicy: string | null;
  policyLabel: string;
  embedding: string;
  collectionName: string;
  pickerTitle: string;
  production: StructuredEvalTarget;
  paths: StructuredEvalTarget[];
}

export interface EvalCatalog {
  structuredEvalSources: EvalReportSource[];
  structuredEvalCatalog: StructuredEvalTarget[];
  structuredEvalPolicyGroups: StructuredEvalPolicyGroup[];
  retrievalEvalReports: RetrievalEvalReportTab[];
  tutorBoardEvalReport: TutorBoardEvalReport | null;
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
  // Longest policy name first so math_object_window_page_anchor beats math_object_window.
  const policies = [...CHUNK_POLICIES].sort((a, b) => b.length - a.length);
  for (const policy of policies) {
    if (rest.startsWith(`${policy}_`)) {
      return policy;
    }
  }
  return null;
}

export function extractCollectionVariant(
  collectionName: string,
  chunkPolicy: string | null,
): string | null {
  if (!chunkPolicy) {
    return null;
  }
  const prefix = `mathbird_chunk_${chunkPolicy}_`;
  if (!collectionName.startsWith(prefix)) {
    return null;
  }
  const remainder = collectionName.slice(prefix.length);
  const match = remainder.match(/_v(\d+)$/);
  return match ? `v${match[1]}` : null;
}

export function chunkPolicyDisplayLabel(
  chunkPolicy: string | null,
  collectionName: string,
): string {
  const base = chunkPolicyLabel(chunkPolicy);
  const variant = extractCollectionVariant(collectionName, chunkPolicy);
  return variant ? `${base} (${variant})` : base;
}

export function chunkPolicyLabel(policy: string | null): string {
  if (!policy) {
    return "Unknown chunk policy";
  }
  return CHUNK_POLICY_LABELS[policy] ?? policy;
}

export function retrievalPathLabel(path: string | null): string {
  if (!path) {
    return "Unknown retrieval path";
  }
  return RETRIEVAL_PATH_LABELS[path] ?? path;
}

function retrievalPathFromTarget(target: EvalTarget): string | null {
  const path = target.metadata.path;
  return typeof path === "string" ? path : null;
}

function buildStructuredLabels(
  target: EvalTarget,
  facets: StructuredEvalTarget["facets"],
  sourceFileName: string,
  reportCreatedAt: string,
): Pick<
  StructuredEvalTarget,
  "comparisonLabel" | "pickerPrimary" | "pickerSecondary" | "pickerTitle"
> {
  const policyLabel = chunkPolicyDisplayLabel(facets.chunkPolicy, target.collectionName);
  const pathLabel = retrievalPathLabel(facets.retrievalPath);
  const comparisonLabel = [policyLabel, facets.embedding, pathLabel].join(" · ");
  return {
    comparisonLabel,
    pickerPrimary: policyLabel,
    pickerSecondary: `${facets.embedding} · ${pathLabel}`,
    pickerTitle: [
      `Collection: ${target.collectionName}`,
      `Source: ${sourceFileName}`,
      `Run: ${reportCreatedAt}`,
    ].join("\n"),
  };
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
      const labels = buildStructuredLabels(
        target,
        facets,
        source.fileName,
        source.report.createdAt,
      );
      catalog.push({
        catalogId: `${source.id}::${target.targetId}`,
        sourceId: source.id,
        sourceFileName: source.fileName,
        reportCreatedAt: source.report.createdAt,
        goldenPath: source.report.goldenPath,
        target,
        facets,
        ...labels,
      });
    }
  }

  return catalog.sort((a, b) => a.comparisonLabel.localeCompare(b.comparisonLabel));
}

const PATH_ORDER = ["production", "structured_only", "semantic_only"] as const;

export type StructuredRetrievalPath = (typeof PATH_ORDER)[number];

export const STRUCTURED_RETRIEVAL_PATHS: ReadonlyArray<{
  id: StructuredRetrievalPath;
  label: string;
}> = [
  { id: "production", label: "Production" },
  { id: "structured_only", label: "Structured" },
  { id: "semantic_only", label: "Semantic" },
];

export function targetsForRetrievalPath(
  groups: readonly StructuredEvalPolicyGroup[],
  path: StructuredRetrievalPath,
): StructuredEvalTarget[] {
  return groups.map((group) => {
    if (path === "production") {
      return group.production;
    }
    return (
      group.paths.find((entry) => entry.facets.retrievalPath === path) ?? group.production
    );
  });
}

export function buildStructuredPolicyGroups(
  sources: readonly EvalReportSource[],
  catalog: readonly StructuredEvalTarget[],
): StructuredEvalPolicyGroup[] {
  const groups: StructuredEvalPolicyGroup[] = [];

  for (const source of sources) {
    const entries = catalog.filter((item) => item.sourceId === source.id);
    const production =
      entries.find((item) => item.facets.retrievalPath === "production") ?? entries[0];
    if (!production) {
      continue;
    }
    const paths = PATH_ORDER.flatMap((path) => {
      const match = entries.find((item) => item.facets.retrievalPath === path);
      return match ? [match] : [];
    });
    groups.push({
      sourceId: source.id,
      sourceFileName: source.fileName,
      reportCreatedAt: source.report.createdAt,
      goldenPath: source.report.goldenPath,
      chunkPolicy: production.facets.chunkPolicy,
      policyLabel: chunkPolicyDisplayLabel(
        production.facets.chunkPolicy,
        production.target.collectionName,
      ),
      embedding: production.facets.embedding,
      collectionName: production.target.collectionName,
      pickerTitle: production.pickerTitle,
      production,
      paths,
    });
  }

  return groups.sort((a, b) => a.policyLabel.localeCompare(b.policyLabel));
}

export function defaultStructuredPolicySelection(
  groups: readonly StructuredEvalPolicyGroup[],
): StructuredEvalPolicyGroup[] {
  return [...groups];
}

export function productionTargetsFromGroups(
  groups: readonly StructuredEvalPolicyGroup[],
): StructuredEvalTarget[] {
  return groups.map((group) => group.production);
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
    a.comparisonLabel.localeCompare(b.comparisonLabel),
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
      label: item.pickerPrimary,
    })),
    failures: [],
  };
}

function buildAxisTabs(
  embeddingModules: Record<string, unknown>,
  chunkingModules: Record<string, unknown>,
  structuredModules: Record<string, unknown>,
  structuredEvalSources: EvalReportSource[],
  structuredEvalPolicyGroups: StructuredEvalPolicyGroup[],
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
      productionTargetsFromGroups(defaultStructuredPolicySelection(structuredEvalPolicyGroups)),
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

function latestTutorBoardReport(
  modules: Record<string, unknown>,
): TutorBoardEvalReport | null {
  const reports = Object.entries(modules)
    .map(([, raw]) => normalizeTutorBoardReport(raw))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return reports[0] ?? null;
}

export async function loadEvalCatalog(): Promise<EvalCatalog> {
  const [embeddingModules, chunkingModules, structuredModules, tutorBoardModules] =
    await Promise.all([
    loadJsonModules(embeddingEvalModules),
    loadJsonModules(chunkingEvalModules),
    loadJsonModules(structuredEvalModules),
    loadJsonModules(tutorBoardEvalModules),
  ]);

  const structuredEvalSources = buildSources(structuredModules);
  const structuredEvalCatalog = buildStructuredEvalCatalog(structuredEvalSources);
  const structuredEvalPolicyGroups = buildStructuredPolicyGroups(
    structuredEvalSources,
    structuredEvalCatalog,
  );
  const retrievalEvalReports = buildAxisTabs(
    embeddingModules,
    chunkingModules,
    structuredModules,
    structuredEvalSources,
    structuredEvalPolicyGroups,
  );

  return {
    structuredEvalSources,
    structuredEvalCatalog,
    structuredEvalPolicyGroups,
    retrievalEvalReports,
    tutorBoardEvalReport: latestTutorBoardReport(tutorBoardModules),
  };
}
