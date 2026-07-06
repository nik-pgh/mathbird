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

function normalizeTutorBoardReport(raw) {
  const report = asRecord(raw);
  return {
    passRate: pick(report, "pass_rate", "passRate", 0),
    cases: Array.isArray(report.cases) ? report.cases : [],
    axisSummaries: Array.isArray(report.axis_summaries ?? report.axisSummaries)
      ? report.axis_summaries ?? report.axisSummaries
      : [],
  };
}

const sample = {
  schema_version: 1,
  comparison_axis: "tutor_board",
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

const normalized = normalizeTutorBoardReport(sample);
assert.equal(normalized.passRate, 0.8);
assert.equal(normalized.cases.length, 1);
assert.equal(normalized.axisSummaries.length, 1);

const generatedPath = join(root, "src/data/tutorBoardEval.generated.json");
try {
  const generated = normalizeTutorBoardReport(
    JSON.parse(readFileSync(generatedPath, "utf8")),
  );
  assert.ok(generated.cases.length > 0, "generated tutor board report should include cases");
} catch (error) {
  if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
    console.log("test-tutor-board-eval: ok (no generated report yet)");
    process.exit(0);
  }
  throw error;
}

console.log("test-tutor-board-eval: ok");
