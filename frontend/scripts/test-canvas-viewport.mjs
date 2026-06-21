import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const sourcePath = new URL("../src/lib/canvasViewport.ts", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

const sandbox = {
  exports: {},
};

vm.runInNewContext(compiled, sandbox, { filename: "canvasViewport.ts" });

const { CANVAS_WHEEL_IGNORE_ATTR, isDeleteShortcutKey, shouldHandleCanvasWheelTarget } =
  sandbox.exports;

assert.equal(CANVAS_WHEEL_IGNORE_ATTR, "data-canvas-wheel-ignore");
assert.equal(typeof shouldHandleCanvasWheelTarget, "function");
assert.equal(isDeleteShortcutKey("Delete"), true);
assert.equal(isDeleteShortcutKey("Backspace"), true);
assert.equal(isDeleteShortcutKey("Enter"), false);

const ignoredTarget = {
  closest(selector) {
    assert.equal(selector, `[${CANVAS_WHEEL_IGNORE_ATTR}]`);
    return { dataset: { canvasWheelIgnore: "true" } };
  },
};

const normalTarget = {
  closest(selector) {
    assert.equal(selector, `[${CANVAS_WHEEL_IGNORE_ATTR}]`);
    return null;
  },
};

assert.equal(shouldHandleCanvasWheelTarget(ignoredTarget), false);
assert.equal(shouldHandleCanvasWheelTarget(normalTarget), true);
assert.equal(shouldHandleCanvasWheelTarget(null), true);
