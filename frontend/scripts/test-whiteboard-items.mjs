import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const sourcePath = new URL("../src/lib/whiteboardItems.ts", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

// whiteboardItems.ts only imports types (erased by transpileModule), so the
// sandbox needs no require stubs.
const sandbox = {
  exports: {},
  require() {
    throw new Error("Unexpected require in whiteboardItems.ts");
  },
};

vm.runInNewContext(compiled, sandbox, { filename: "whiteboardItems.ts" });

const { parseAiBoardItem, parseAiBoardItems } = sandbox.exports;

assert.equal(typeof parseAiBoardItem, "function");
assert.equal(typeof parseAiBoardItems, "function");

// Objects returned from the vm sandbox live in a different realm (different
// Object.prototype), which trips `deepStrictEqual` ("same structure but not
// reference-equal"). Round-tripping through JSON re-creates them in this realm.
function clone(value) {
  return JSON.parse(JSON.stringify(value));
}
function deepEqual(actual, expected) {
  assert.deepEqual(clone(actual), expected);
}

// --- text ---
const text = parseAiBoardItem({
  kind: "text",
  id: "eq1",
  markdown: "$2x + 5 = 10$",
});
deepEqual(text, {
  kind: "text",
  id: "eq1",
  markdown: "$2x + 5 = 10$",
});

// --- plot (with optional label) ---
const plot = parseAiBoardItem({
  kind: "plot",
  id: "p1",
  expression: "x**2",
  x_min: -10,
  x_max: 10,
  label: "Parabola",
});
deepEqual(plot, {
  kind: "plot",
  id: "p1",
  expression: "x**2",
  x_min: -10,
  x_max: 10,
  label: "Parabola",
});

// --- plot (label omitted -> no label key) ---
const plotNoLabel = parseAiBoardItem({
  kind: "plot",
  id: "p2",
  expression: "sin(x)",
  x_min: -3.14,
  x_max: 3.14,
});
assert.ok(!("label" in plotNoLabel), "plot should not carry label when absent");

// --- shape ---
const shape = parseAiBoardItem({
  kind: "shape",
  id: "s1",
  svg: "<line x1='0' y1='0' x2='10' y2='10'/>",
});
deepEqual(shape, {
  kind: "shape",
  id: "s1",
  svg: "<line x1='0' y1='0' x2='10' y2='10'/>",
});

// --- diagram (mermaid, with label) ---
const diagram = parseAiBoardItem({
  kind: "diagram",
  id: "d1",
  syntax: "mermaid",
  source: "flowchart TD\n  a --> b",
  label: "Tree",
});
deepEqual(diagram, {
  kind: "diagram",
  id: "d1",
  syntax: "mermaid",
  source: "flowchart TD\n  a --> b",
  label: "Tree",
});

// --- diagram syntax defaults to mermaid when missing ---
const diagramNoSyntax = parseAiBoardItem({
  kind: "diagram",
  id: "d2",
  source: "flowchart TD\n  c --> d",
});
assert.equal(diagramNoSyntax.syntax, "mermaid");

// --- rejections ---
assert.equal(parseAiBoardItem(null), null, "non-record -> null");
assert.equal(parseAiBoardItem("text"), null, "non-object -> null");
assert.equal(
  parseAiBoardItem({ kind: "unknown", id: "x" }),
  null,
  "unknown kind -> null",
);
assert.equal(
  parseAiBoardItem({ id: "eq1", markdown: "hi" }),
  null,
  "missing kind -> null",
);
assert.equal(
  parseAiBoardItem({ kind: "text", markdown: "no id" }),
  null,
  "text missing id -> null",
);
assert.equal(
  parseAiBoardItem({ kind: "text", id: "eq1" }),
  null,
  "text missing markdown -> null",
);
assert.equal(
  parseAiBoardItem({ kind: "plot", id: "p", expression: "x" }),
  null,
  "plot missing x_min/x_max -> null",
);
assert.equal(
  parseAiBoardItem({ kind: "plot", id: "p", expression: "x", x_min: "a", x_max: 1 }),
  null,
  "plot non-numeric bounds -> null",
);
assert.equal(
  parseAiBoardItem({ kind: "shape", id: "s" }),
  null,
  "shape missing svg -> null",
);
assert.equal(
  parseAiBoardItem({ kind: "diagram", id: "d", syntax: "graphviz", source: "x" }),
  null,
  "diagram non-mermaid syntax -> null",
);
assert.equal(
  parseAiBoardItem({ kind: 123, id: "x" }),
  null,
  "non-string kind -> null",
);

// --- NaN / Infinity bounds rejected ---
assert.equal(
  parseAiBoardItem({ kind: "plot", id: "p", expression: "x", x_min: NaN, x_max: 1 }),
  null,
  "NaN bound -> null",
);

// --- list parsing filters malformed entries, preserves good ones ---
const list = parseAiBoardItems([
  { kind: "text", id: "t1", markdown: "hello" },
  { kind: "bogus", id: "x" },
  { kind: "plot", id: "p1", expression: "x", x_min: 0, x_max: 1 },
  null,
  "string",
  { kind: "text", id: "no-markdown" },
]);
assert.equal(list.length, 2);
assert.equal(list[0].kind, "text");
assert.equal(list[1].kind, "plot");

// --- empty list ---
assert.deepEqual(parseAiBoardItems([]), []);

console.log("whiteboard-items tests passed");
