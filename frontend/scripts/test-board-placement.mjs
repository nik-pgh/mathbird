import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const sourcePath = new URL("../src/lib/boardPlacement.ts", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

const sandbox = { exports: {} };
vm.runInNewContext(compiled, sandbox, { filename: "boardPlacement.ts" });

const { findOpenBoardPosition, rectsOverlap, tutorCardSizeForKind } = sandbox.exports;
const plain = (value) => JSON.parse(JSON.stringify(value));

assert.equal(rectsOverlap({ x: 0, y: 0, width: 100, height: 100 }, { x: 99, y: 0, width: 100, height: 100 }), true);
assert.equal(rectsOverlap({ x: 0, y: 0, width: 100, height: 100 }, { x: 120, y: 0, width: 100, height: 100 }), false);

const first = findOpenBoardPosition({
  size: { width: 320, height: 180 },
  occupied: [],
  viewport: { x: 0, y: 0, width: 900, height: 600 },
});
assert.deepEqual(plain(first), { x: 36, y: 36 });

const second = findOpenBoardPosition({
  size: { width: 320, height: 180 },
  occupied: [{ x: 36, y: 36, width: 320, height: 180 }],
  viewport: { x: 0, y: 0, width: 900, height: 600 },
});
assert.notDeepEqual(plain(second), { x: 36, y: 36 });

assert.deepEqual(plain(tutorCardSizeForKind("text")), { width: 340, height: 180 });
assert.deepEqual(plain(tutorCardSizeForKind("plot")), { width: 360, height: 250 });
assert.deepEqual(plain(tutorCardSizeForKind("shape")), { width: 340, height: 240 });
assert.deepEqual(plain(tutorCardSizeForKind("diagram")), { width: 380, height: 260 });
