import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function pick(record, snakeKey, camelKey, fallback) {
  return record[snakeKey] ?? record[camelKey] ?? fallback;
}

function extractVariantFromFileName(fileName) {
  const match = fileName.match(/^tutorBoardEval\.(.+)\.generated\.json$/);
  return match ? match[1] : null;
}

function normalizeTutorBoardReport(raw, options = {}) {
  const report = asRecord(raw);
  const fileVariant = options.fileName
    ? extractVariantFromFileName(options.fileName)
    : null;
  return {
    targetId: pick(report, "target_id", "targetId", fileVariant ?? "default"),
    label: pick(report, "label", "label", fileVariant ?? "default"),
    metadata: asRecord(report.metadata),
    passRate: pick(report, "pass_rate", "passRate", 0),
    cases: Array.isArray(report.cases) ? report.cases : [],
    axisSummaries: Array.isArray(report.axis_summaries ?? report.axisSummaries)
      ? report.axis_summaries ?? report.axisSummaries
      : [],
  };
}

assert.equal(
  extractVariantFromFileName("tutorBoardEval.baseline.generated.json"),
  "baseline",
);
assert.equal(extractVariantFromFileName("tutorBoardEval.generated.json"), null);

const sample = {
  schema_version: 1,
  comparison_axis: "tutor_board",
  target_id: "baseline",
  label: "Baseline",
  metadata: { board_extractor_timeout_seconds: 4 },
  created_at: "20260706T163635Z",
  golden_path: "evals/golden/tutor_board.jsonl",
  extractor_model: "gpt-4o-mini",
  pass_rate: 0.8,
  axis_summaries: [{ axis: "usage", total: 5, passed: 4, pass_rate: 0.8 }],
  cases: [
    {
      case_id: "tb-use-001",
      axis: "usage",
      description: "Equation setup should create a tutor card",
      passed: true,
      failures: [],
      actual_items: [{ kind: "text", id: "eq1" }],
      tutor_utterance: null,
    },
  ],
  failures: [],
};

const normalized = normalizeTutorBoardReport(sample, {
  fileName: "tutorBoardEval.baseline.generated.json",
});
assert.equal(normalized.targetId, "baseline");
assert.equal(normalized.label, "Baseline");
assert.equal(normalized.passRate, 0.8);
assert.equal(normalized.cases.length, 1);
assert.equal(normalized.axisSummaries.length, 1);
assert.equal(normalized.metadata.board_extractor_timeout_seconds, 4);

const baselinePath = join(root, "src/data/tutorBoardEval.baseline.generated.json");
try {
  const generated = normalizeTutorBoardReport(
    JSON.parse(readFileSync(baselinePath, "utf8")),
    { fileName: "tutorBoardEval.baseline.generated.json" },
  );
  assert.equal(generated.targetId, "baseline");
  assert.ok(generated.cases.length > 0, "baseline tutor board report should include cases");
} catch (error) {
  if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
    console.log("test-tutor-board-eval: ok (no baseline report yet)");
    process.exit(0);
  }
  throw error;
}

console.log("test-tutor-board-eval: ok");
