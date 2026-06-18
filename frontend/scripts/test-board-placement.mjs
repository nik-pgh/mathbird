import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const sourcePath = new URL("../src/lib/boardPlacement.ts", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8");
const compileTs = (sourceText) => ts.transpileModule(sourceText, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

const sandbox = { exports: {} };
vm.runInNewContext(compileTs(source), sandbox, { filename: "boardPlacement.ts" });

const { findOpenBoardPosition, rectsOverlap, tutorCardSizeForKind } = sandbox.exports;
const plain = (value) => JSON.parse(JSON.stringify(value));
const rectAt = (position, size) => ({ ...plain(position), ...size });
const assertNoOverlap = (candidate, occupied) => {
  for (const rect of occupied) {
    assert.equal(
      rectsOverlap(candidate, rect),
      false,
      `expected ${JSON.stringify(candidate)} not to overlap ${JSON.stringify(rect)}`,
    );
  }
};

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
assert.deepEqual(plain(second), { x: 384, y: 36 });
assertNoOverlap(
  rectAt(second, { width: 320, height: 180 }),
  [{ x: 36, y: 36, width: 320, height: 180 }],
);

const defaultStudentSize = { width: 520, height: 390 };
const defaultStudentOccupied = [{ x: 36, y: 36, ...defaultStudentSize }];
const fallbackStudent = findOpenBoardPosition({
  size: defaultStudentSize,
  occupied: defaultStudentOccupied,
  viewport: { x: 0, y: 0, width: 900, height: 600 },
});
assert.deepEqual(plain(fallbackStudent), { x: 584, y: 36 });
assertNoOverlap(rectAt(fallbackStudent, defaultStudentSize), defaultStudentOccupied);

const fullVisibleGridOccupied = [
  { x: 36, y: 36, width: 320, height: 180 },
  { x: 384, y: 36, width: 320, height: 180 },
  { x: 36, y: 244, width: 320, height: 180 },
  { x: 384, y: 244, width: 320, height: 180 },
];
const fallbackOutsideVisibleGrid = findOpenBoardPosition({
  size: { width: 320, height: 180 },
  occupied: fullVisibleGridOccupied,
  viewport: { x: 0, y: 0, width: 900, height: 600 },
});
assert.deepEqual(plain(fallbackOutsideVisibleGrid), { x: 732, y: 36 });
assertNoOverlap(
  rectAt(fallbackOutsideVisibleGrid, { width: 320, height: 180 }),
  fullVisibleGridOccupied,
);

assert.deepEqual(plain(tutorCardSizeForKind("text")), { width: 340, height: 180 });
assert.deepEqual(plain(tutorCardSizeForKind("plot")), { width: 360, height: 250 });
assert.deepEqual(plain(tutorCardSizeForKind("shape")), { width: 340, height: 240 });
assert.deepEqual(plain(tutorCardSizeForKind("diagram")), { width: 380, height: 260 });

const reducerPath = new URL("../src/components/session/workspaceReducer.ts", import.meta.url);
const reducerSource = fs.readFileSync(reducerPath, "utf8");
const reducerModule = { exports: {} };
const reducerSandbox = {
  exports: reducerModule.exports,
  module: reducerModule,
  require(specifier) {
    if (specifier === "../../lib/boardPlacement") return sandbox.exports;
    throw new Error(`Unexpected reducer import: ${specifier}`);
  },
};
vm.runInNewContext(compileTs(reducerSource), reducerSandbox, {
  filename: "workspaceReducer.ts",
});

const { initialWorkspaceState, workspaceReducer } = reducerModule.exports;
const textItem = { kind: "text", id: "tutor-text-1", markdown: "Solve x + 2 = 5" };
const withTutorObject = workspaceReducer(initialWorkspaceState, {
  type: "ai_upsert",
  items: [textItem],
});
const tutorObject = withTutorObject.objects[0];
assert.deepEqual(plain(tutorObject.size), { width: 340, height: 180 });
assert.deepEqual(plain(tutorObject.position), { x: 772, y: 36 });
assertNoOverlap(
  rectAt(tutorObject.position, tutorObject.size),
  initialWorkspaceState.studentCards.map((card) => rectAt(card.position, card.size)),
);

const movedTutorObject = { ...tutorObject, position: { x: 420, y: 240 }, size: { width: 410, height: 210 } };
const afterExistingUpsert = workspaceReducer(
  { ...withTutorObject, objects: [movedTutorObject] },
  { type: "ai_upsert", items: [{ ...textItem, markdown: "Updated" }] },
);
assert.deepEqual(plain(afterExistingUpsert.objects[0].position), { x: 420, y: 240 });
assert.deepEqual(plain(afterExistingUpsert.objects[0].size), { width: 410, height: 210 });

const shapeItem = { kind: "shape", id: "tutor-shape-1", svg: "<svg></svg>" };
const withSecondTutorObject = workspaceReducer(
  { ...withTutorObject, objects: [movedTutorObject] },
  { type: "ai_upsert", items: [shapeItem] },
);
const shapeObject = withSecondTutorObject.objects.find((object) => object.id === shapeItem.id);
assertNoOverlap(
  rectAt(shapeObject.position, shapeObject.size),
  withSecondTutorObject.objects
    .filter((object) => object.id !== shapeItem.id)
    .map((object) => rectAt(object.position, object.size)),
);
