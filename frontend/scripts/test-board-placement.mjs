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

const {
  COLLAPSED_TUTOR_RIBBON_HEIGHT,
  clampTutorCardSize,
  deriveTutorBoardTitle,
  layoutTutorFlow,
  tutorFlowItemHeight,
  tutorFlowMaxColumnHeight,
} = sandbox.exports;

assert.equal(COLLAPSED_TUTOR_RIBBON_HEIGHT, 44);

assert.deepEqual(
  plain(clampTutorCardSize({ width: 100, height: 90 })),
  { width: 280, height: 180 },
);
assert.deepEqual(
  plain(clampTutorCardSize({ width: 900, height: 800 })),
  { width: 720, height: 520 },
);
assert.deepEqual(
  plain(clampTutorCardSize({ width: 360, height: 250 })),
  { width: 360, height: 250 },
);

assert.equal(tutorFlowMaxColumnHeight(400), 520);
assert.equal(tutorFlowMaxColumnHeight(900), 828);
assert.equal(
  tutorFlowItemHeight({ id: "collapsed", collapsed: true, size: { width: 340, height: 180 } }),
  44,
);
assert.equal(
  tutorFlowItemHeight({ id: "expanded", collapsed: false, size: { width: 340, height: 180 } }),
  180,
);

assert.equal(
  deriveTutorBoardTitle({ kind: "plot", id: "plot-1", expression: "y=x", x_min: -5, x_max: 5, label: "Linear graph" }, 3),
  "Linear graph",
);
assert.equal(
  deriveTutorBoardTitle({ kind: "diagram", id: "diagram-1", syntax: "mermaid", source: "graph TD;A-->B", label: "Factor tree" }, 4),
  "Factor tree",
);
assert.equal(
  deriveTutorBoardTitle({ kind: "text", id: "text-2", markdown: "### Perfect square factor\n54 = 2 x 27" }, 5),
  "Perfect square factor",
);
assert.equal(
  deriveTutorBoardTitle({ kind: "text", id: "text-3", markdown: "Intro body\nstill body\n## Heading Title" }, 6),
  "Heading Title",
);
assert.equal(
  deriveTutorBoardTitle({ kind: "shape", id: "shape-1", svg: "<svg></svg>" }, 6),
  "Sketch 6",
);
assert.equal(
  deriveTutorBoardTitle({ kind: "shape", id: "shape-2", svg: "<svg></svg>", label: "Ignored" }, 7),
  "Sketch 7",
);

const flow = layoutTutorFlow({
  origin: { x: 36, y: 36 },
  maxColumnHeight: 240,
  items: [
    { id: "a", collapsed: true, size: { width: 340, height: 180 } },
    { id: "b", collapsed: false, size: { width: 340, height: 180 } },
    { id: "c", collapsed: true, size: { width: 380, height: 260 } },
  ],
});
assert.deepEqual(plain(flow.positions.a), { x: 36, y: 36 });
assert.deepEqual(plain(flow.positions.b), { x: 36, y: 90 });
assert.deepEqual(plain(flow.positions.c), { x: 400, y: 36 });
assert.equal(flow.width, 744);
assert.equal(flow.height, 234);

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
assert.deepEqual(plain(tutorObject.position), { x: 36, y: 36 });
assert.equal(tutorObject.collapsed, false);

const movedTutorObject = { ...tutorObject, position: { x: 420, y: 240 }, size: { width: 410, height: 210 } };
const afterExistingUpsert = workspaceReducer(
  { ...withTutorObject, objects: [movedTutorObject] },
  { type: "ai_upsert", items: [{ ...textItem, markdown: "Updated" }] },
);
assert.deepEqual(plain(afterExistingUpsert.objects[0].position), { x: 420, y: 240 });
assert.deepEqual(plain(afterExistingUpsert.objects[0].size), { width: 410, height: 210 });
assert.equal(afterExistingUpsert.objects[0].collapsed, false);

const shapeItem = { kind: "shape", id: "tutor-shape-1", svg: "<svg></svg>" };
const withSecondTutorObject = workspaceReducer(
  { ...withTutorObject, objects: [movedTutorObject] },
  { type: "ai_upsert", items: [shapeItem] },
);
const shapeObject = withSecondTutorObject.objects.find((object) => object.id === shapeItem.id);
const collapsedTextObject = withSecondTutorObject.objects.find((object) => object.id === textItem.id);
assert.deepEqual(plain(shapeObject.position), { x: 420, y: 294 });
assert.deepEqual(plain(shapeObject.size), { width: 340, height: 240 });
assert.equal(shapeObject.collapsed, false);
assert.equal(collapsedTextObject.collapsed, true);

const afterActivation = workspaceReducer(withSecondTutorObject, {
  type: "activate_object",
  id: textItem.id,
});
assert.equal(afterActivation.objects.find((object) => object.id === textItem.id).collapsed, false);
assert.equal(afterActivation.objects.find((object) => object.id === shapeItem.id).collapsed, true);

const thirdTextItem = { kind: "text", id: "tutor-text-3", markdown: "### New radical step\nsqrt(54)" };
const flowState = workspaceReducer(
  afterActivation,
  {
    type: "ai_upsert",
    items: [thirdTextItem],
    boardSize: { width: 900, height: 260 },
  },
);
assert.equal(flowState.objects.find((object) => object.id === textItem.id).collapsed, true);
assert.equal(flowState.objects.find((object) => object.id === shapeItem.id).collapsed, true);
assert.equal(flowState.objects.find((object) => object.id === thirdTextItem.id).collapsed, false);
assert.deepEqual(
  plain(flowState.objects.map((object) => object.position)),
  [
    { x: 420, y: 240 },
    { x: 420, y: 294 },
    { x: 420, y: 348 },
  ],
);

const resizedTutor = workspaceReducer(flowState, {
  type: "resize_object",
  id: thirdTextItem.id,
  size: { width: 760, height: 560 },
  boardSize: { width: 900, height: 700 },
});
assert.deepEqual(
  plain(resizedTutor.objects.find((object) => object.id === thirdTextItem.id).size),
  { width: 720, height: 520 },
);

const relabeled = workspaceReducer(resizedTutor, {
  type: "rename_student_card",
  id: "student-card-1",
  label: "Exercise 4.2: radicals",
});
assert.equal(
  relabeled.studentCards.find((card) => card.id === "student-card-1").label,
  "Exercise 4.2: radicals",
);

const blankRelabel = workspaceReducer(relabeled, {
  type: "rename_student_card",
  id: "student-card-1",
  label: "   ",
});
assert.equal(
  blankRelabel.studentCards.find((card) => card.id === "student-card-1").label,
  "Student Card 1",
);

const tutorLayerPath = new URL("../src/components/session/TutorObjectLayer.tsx", import.meta.url);
const tutorLayerSource = fs.readFileSync(tutorLayerPath, "utf8");
assert.match(tutorLayerSource, /tutor-object-collapsed/);
assert.match(tutorLayerSource, /onActivateObject/);
assert.doesNotMatch(tutorLayerSource, /height:\s*object\.size\?\.height/);

const workspaceTypesPath = new URL("../src/components/session/workspaceTypes.ts", import.meta.url);
const workspaceTypesSource = fs.readFileSync(workspaceTypesPath, "utf8");
assert.match(workspaceTypesSource, /collapsed\?:\s*boolean/);
assert.match(workspaceTypesSource, /activate_object/);

const workspacePath = new URL("../src/components/session/SharedReasoningWorkspace.tsx", import.meta.url);
const workspaceSource = fs.readFileSync(workspacePath, "utf8");
assert.match(workspaceSource, /SquarePen/);
assert.match(workspaceSource, /aria-label="Add student card"/);
assert.doesNotMatch(workspaceSource, />\s*Student Card\s*<\/button>/);

const sessionCssPath = new URL("../src/styles/session.css", import.meta.url);
const sessionCss = fs.readFileSync(sessionCssPath, "utf8");
assert.match(sessionCss, /\.tutor-focus-rail/s);
assert.match(sessionCss, /\.tutor-object-expanded\s*\{[^}]*max-height:/s);
assert.match(sessionCss, /\.tutor-object-body\s*\{[^}]*min-height:\s*0;[^}]*overflow:\s*auto;/s);
assert.doesNotMatch(sessionCss, /\.tutor-object\s*\{[^}]*height:\s*180px;/s);
