/**
 * Narrow loosely-typed board-item records (from eval report JSON) into the
 * typed {@link AiBoardItem} union consumed by the whiteboard renderer.
 *
 * The tutor-board eval report carries each extractor output as
 * `Record<string, unknown>` (it is untyped on the TS side), but its runtime
 * shape mirrors the four pydantic models in
 * `backend/app/agent/whiteboard/messages.py`. These helpers validate and
 * refine each record, dropping anything malformed so the renderer only ever
 * sees well-formed items.
 */

import type {
  AiBoardDiagram,
  AiBoardItem,
  AiBoardPlot,
  AiBoardShape,
  AiBoardText,
} from "./whiteboard";

type RawRecord = Record<string, unknown>;

const KNOWN_KINDS = new Set(["text", "plot", "shape", "diagram"]);

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isRecord(value: unknown): value is RawRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function parseText(record: RawRecord): AiBoardText | null {
  const { id, markdown } = record;
  if (!isString(id) || !isString(markdown)) return null;
  return { kind: "text", id, markdown };
}

function parsePlot(record: RawRecord): AiBoardPlot | null {
  const { id, expression, x_min, x_max, label } = record;
  if (!isString(id) || !isString(expression)) return null;
  if (!isNumber(x_min) || !isNumber(x_max)) return null;
  const item: AiBoardPlot = { kind: "plot", id, expression, x_min, x_max };
  if (isString(label)) item.label = label;
  return item;
}

function parseShape(record: RawRecord): AiBoardShape | null {
  const { id, svg } = record;
  if (!isString(id) || !isString(svg)) return null;
  return { kind: "shape", id, svg };
}

function parseDiagram(record: RawRecord): AiBoardDiagram | null {
  const { id, syntax, source, label } = record;
  if (!isString(id) || !isString(source)) return null;
  // `syntax` defaults to "mermaid" on the backend; only that value is valid today.
  const resolvedSyntax = isString(syntax) ? syntax : "mermaid";
  if (resolvedSyntax !== "mermaid") return null;
  const item: AiBoardDiagram = {
    kind: "diagram",
    id,
    syntax: "mermaid",
    source,
  };
  if (isString(label)) item.label = label;
  return item;
}

/**
 * Validate a single raw record into a typed board item.
 * Returns `null` for unknown kinds or records missing required fields, so
 * callers can `filter` without try/catch.
 */
export function parseAiBoardItem(record: unknown): AiBoardItem | null {
  if (!isRecord(record)) return null;
  const kind = record.kind;
  if (!isString(kind) || !KNOWN_KINDS.has(kind)) return null;
  switch (kind) {
    case "text":
      return parseText(record);
    case "plot":
      return parsePlot(record);
    case "shape":
      return parseShape(record);
    case "diagram":
      return parseDiagram(record);
    default:
      return null;
  }
}

/** Validate a list of raw records, dropping anything malformed. */
export function parseAiBoardItems(records: readonly unknown[]): AiBoardItem[] {
  return records
    .map((record) => parseAiBoardItem(record))
    .filter((item): item is AiBoardItem => item !== null);
}
