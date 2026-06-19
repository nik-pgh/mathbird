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
  "Intro body",
);
const longMathTitle = "\\(a_1+a_2+a_3+a_4+a_5+a_6+a_7+a_8+a_9+a_{10}=55\\)";
assert.equal(
  deriveTutorBoardTitle({ kind: "text", id: "text-4", markdown: longMathTitle }, 7),
  longMathTitle,
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
const retainedTextObject = withSecondTutorObject.objects.find((object) => object.id === textItem.id);
assert.deepEqual(plain(shapeObject.position), { x: 420, y: 460 });
assert.deepEqual(plain(shapeObject.size), { width: 340, height: 240 });
assert.equal(shapeObject.collapsed, false);
assert.equal(retainedTextObject.collapsed, false);

const afterActivation = workspaceReducer(withSecondTutorObject, {
  type: "activate_object",
  id: textItem.id,
});
assert.equal(afterActivation.objects.find((object) => object.id === textItem.id).collapsed, false);
assert.equal(afterActivation.objects.find((object) => object.id === shapeItem.id).collapsed, false);

const afterCollapse = workspaceReducer(afterActivation, {
  type: "collapse_object",
  id: textItem.id,
  boardSize: { width: 900, height: 700 },
});
assert.equal(afterCollapse.objects.find((object) => object.id === textItem.id).collapsed, true);
assert.equal(afterCollapse.objects.find((object) => object.id === shapeItem.id).collapsed, false);

const thirdTextItem = { kind: "text", id: "tutor-text-3", markdown: "### New radical step\nsqrt(54)" };
const flowState = workspaceReducer(
  afterActivation,
  {
    type: "ai_upsert",
    items: [thirdTextItem],
    boardSize: { width: 900, height: 260 },
  },
);
assert.equal(flowState.objects.find((object) => object.id === textItem.id).collapsed, false);
assert.equal(flowState.objects.find((object) => object.id === shapeItem.id).collapsed, false);
assert.equal(flowState.objects.find((object) => object.id === thirdTextItem.id).collapsed, false);
assert.deepEqual(
  plain(flowState.objects.map((object) => object.position)),
  [
    { x: 420, y: 240 },
    { x: 420, y: 460 },
    { x: 854, y: 240 },
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

const firstTutorMoved = workspaceReducer(resizedTutor, {
  type: "move_object",
  id: textItem.id,
  position: { x: 450, y: 260 },
});
assert.deepEqual(
  plain(firstTutorMoved.objects.map((object) => object.position)),
  [
    { x: 450, y: 260 },
    { x: 420, y: 460 },
    { x: 854, y: 240 },
  ],
);

const secondTutorMoved = workspaceReducer(resizedTutor, {
  type: "move_object",
  id: shapeItem.id,
  position: { x: 390, y: 304 },
});
assert.deepEqual(
  plain(secondTutorMoved.objects.map((object) => object.position)),
  [
    { x: 420, y: 240 },
    { x: 390, y: 304 },
    { x: 854, y: 240 },
  ],
);

const unknownTutorMoved = workspaceReducer(resizedTutor, {
  type: "move_object",
  id: "missing-tutor-object",
  position: { x: 20, y: 20 },
});
assert.equal(unknownTutorMoved, resizedTutor);
assert.deepEqual(
  plain(unknownTutorMoved.objects.map((object) => object.position)),
  plain(resizedTutor.objects.map((object) => object.position)),
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

const withStickyNote = workspaceReducer(initialWorkspaceState, {
  type: "add_sticky_note",
  boardSize: { width: 900, height: 600 },
});
assert.equal(Array.isArray(withStickyNote.stickyNotes), true);
assert.equal(withStickyNote.stickyNotes.length, 1);
assert.equal(withStickyNote.stickyNotes[0].id, "sticky-note-1");
assert.equal(withStickyNote.stickyNotes[0].text, "");
assert.deepEqual(plain(withStickyNote.stickyNotes[0].size), { width: 220, height: 160 });

const movedStickyNote = workspaceReducer(withStickyNote, {
  type: "move_sticky_note",
  id: "sticky-note-1",
  position: { x: 460, y: 280 },
});
assert.deepEqual(
  plain(movedStickyNote.stickyNotes.find((note) => note.id === "sticky-note-1").position),
  { x: 460, y: 280 },
);

const updatedStickyNote = workspaceReducer(movedStickyNote, {
  type: "update_sticky_note_text",
  id: "sticky-note-1",
  text: "Try factoring first",
});
assert.equal(
  updatedStickyNote.stickyNotes.find((note) => note.id === "sticky-note-1").text,
  "Try factoring first",
);

const resizedStickyNote = workspaceReducer(updatedStickyNote, {
  type: "resize_sticky_note",
  id: "sticky-note-1",
  size: { width: 120, height: 90 },
});
assert.deepEqual(
  plain(resizedStickyNote.stickyNotes.find((note) => note.id === "sticky-note-1").size),
  { width: 160, height: 120 },
);

const maxResizedStickyNote = workspaceReducer(updatedStickyNote, {
  type: "resize_sticky_note",
  id: "sticky-note-1",
  size: { width: 900, height: 800 },
});
assert.deepEqual(
  plain(maxResizedStickyNote.stickyNotes.find((note) => note.id === "sticky-note-1").size),
  { width: 420, height: 360 },
);

const withInkColor = workspaceReducer(resizedStickyNote, {
  type: "set_ink_color",
  color: "#ff775f",
});
assert.equal(withInkColor.ink.color, "#ff775f");

const withInkTool = workspaceReducer(withInkColor, {
  type: "set_ink_tool",
  tool: "eraser",
});
assert.equal(withInkTool.ink.tool, "eraser");

const privateStroke = {
  id: "private-stroke-1",
  target: { kind: "private_board" },
  tool: "pen",
  color: "#2f6fed",
  points: [[10, 20, 0], [14, 24, 8]],
};
const withPrivateStroke = workspaceReducer(withInkTool, {
  type: "commit_private_board_stroke",
  stroke: privateStroke,
});
assert.equal(withPrivateStroke.privateBoardStrokes.length, 1);
assert.deepEqual(plain(withPrivateStroke.privateBoardStrokes[0]), privateStroke);
assert.deepEqual(plain(withPrivateStroke.ink.activeTarget), { kind: "private_board" });

const afterUndoInk = workspaceReducer(withPrivateStroke, { type: "undo_active_ink" });
assert.equal(afterUndoInk.privateBoardStrokes.length, 0);

const withTwoPrivateStrokes = workspaceReducer(
  workspaceReducer(afterUndoInk, {
    type: "commit_private_board_stroke",
    stroke: privateStroke,
  }),
  {
    type: "commit_private_board_stroke",
    stroke: { ...privateStroke, id: "private-stroke-2" },
  },
);
const afterClearInk = workspaceReducer(withTwoPrivateStrokes, { type: "clear_active_ink" });
assert.equal(afterClearInk.privateBoardStrokes.length, 0);

const withStudentCardInkTarget = workspaceReducer(withTwoPrivateStrokes, {
  type: "set_active_ink_target",
  target: { kind: "student_card", cardId: "student-card-1" },
});
assert.deepEqual(
  plain(withStudentCardInkTarget.ink.activeTarget),
  { kind: "student_card", cardId: "student-card-1" },
);
const afterStudentTargetUndo = workspaceReducer(withStudentCardInkTarget, { type: "undo_active_ink" });
assert.equal(afterStudentTargetUndo.privateBoardStrokes.length, 2);
const afterStudentTargetClear = workspaceReducer(withStudentCardInkTarget, { type: "clear_active_ink" });
assert.equal(afterStudentTargetClear.privateBoardStrokes.length, 2);

const tutorLayerPath = new URL("../src/components/session/TutorObjectLayer.tsx", import.meta.url);
const tutorLayerSource = fs.readFileSync(tutorLayerPath, "utf8");
assert.match(tutorLayerSource, /objects\.map/);
assert.match(tutorLayerSource, /deriveTutorBoardTitle/);
assert.match(tutorLayerSource, /renderMathTextToHtml/);
assert.match(tutorLayerSource, /DOMPurify\.sanitize/);
assert.match(tutorLayerSource, /onResizeObject/);
assert.match(tutorLayerSource, /tutor-object-resize/);
assert.match(tutorLayerSource, /onCollapseObject/);
assert.match(tutorLayerSource, /tutor-object-title-action/);
assert.match(tutorLayerSource, /Maximize2/);
assert.match(tutorLayerSource, /Minimize2/);
assert.match(tutorLayerSource, /onKeyDown/);
assert.match(tutorLayerSource, /ArrowRight/);
assert.match(tutorLayerSource, /ArrowLeft/);
assert.match(tutorLayerSource, /ArrowDown/);
assert.match(tutorLayerSource, /ArrowUp/);
assert.doesNotMatch(tutorLayerSource, /role=\{isCollapsed \? "button" : undefined\}/);
assert.doesNotMatch(tutorLayerSource, /tabIndex=\{isCollapsed \? 0 : undefined\}/);
assert.match(tutorLayerSource, /onLostPointerCapture=\{endResize\}/);
assert.doesNotMatch(tutorLayerSource, /activeObject\s*=/);
assert.doesNotMatch(tutorLayerSource, /tutor-object-history/);
assert.doesNotMatch(
  tutorLayerSource,
  /className="tutor-object-resize"[\s\S]*?style=\{\{/,
);

const workspaceTypesPath = new URL("../src/components/session/workspaceTypes.ts", import.meta.url);
const workspaceTypesSource = fs.readFileSync(workspaceTypesPath, "utf8");
assert.match(workspaceTypesSource, /collapsed\?:\s*boolean/);
assert.match(workspaceTypesSource, /activate_object/);
assert.match(workspaceTypesSource, /collapse_object/);
assert.match(workspaceTypesSource, /InkTarget[\s\S]*kind:\s*"private_board"[\s\S]*kind:\s*"student_card";\s*cardId:\s*string/);
assert.doesNotMatch(workspaceTypesSource, /cardId\?:\s*string/);
assert.match(workspaceTypesSource, /PrivateBoardInkStroke extends Omit<InkStroke, "target">/);
assert.match(workspaceTypesSource, /privateBoardStrokes:\s*PrivateBoardInkStroke\[\]/);
assert.match(workspaceTypesSource, /commit_private_board_stroke";\s*stroke:\s*PrivateBoardInkStroke/);

const workspacePath = new URL("../src/components/session/SharedReasoningWorkspace.tsx", import.meta.url);
const workspaceSource = fs.readFileSync(workspacePath, "utf8");
assert.match(workspaceSource, /boardSize: getBoardSize\(\)/);
assert.match(workspaceSource, /resizeObject/);
assert.match(workspaceSource, /onResizeObject=\{resizeObject\}/);
assert.match(workspaceSource, /collapseObject/);
assert.match(workspaceSource, /onCollapseObject=\{collapseObject\}/);
assert.match(workspaceSource, /import BoardInkToolbar from "\.\/BoardInkToolbar"/);
assert.match(workspaceSource, /import PrivateBoardInkLayer from "\.\/PrivateBoardInkLayer"/);
assert.match(workspaceSource, /const setInkTool = useCallback/);
assert.match(workspaceSource, /dispatch\(\{ type: "set_ink_tool", tool \}\)/);
assert.match(workspaceSource, /const setInkColor = useCallback/);
assert.match(workspaceSource, /dispatch\(\{ type: "set_ink_color", color \}\)/);
assert.match(workspaceSource, /const commitPrivateBoardStroke = useCallback/);
assert.match(workspaceSource, /dispatch\(\{ type: "commit_private_board_stroke", stroke \}\)/);
assert.match(workspaceSource, /const setActiveInkTarget = useCallback/);
assert.match(workspaceSource, /dispatch\(\{ type: "set_active_ink_target", target \}\)/);
assert.match(workspaceSource, /const undoActiveInk = useCallback/);
assert.match(workspaceSource, /const activeTarget = state\.ink\.activeTarget;[\s\S]*?activeTarget\.kind === "student_card"[\s\S]*?setInkCommand\(\{[\s\S]*?target: activeTarget[\s\S]*?action: "undo"/);
assert.match(workspaceSource, /activeTarget\.kind === "private_board"[\s\S]*?dispatch\(\{ type: "undo_active_ink" \}\)/);
assert.match(workspaceSource, /const clearActiveInk = useCallback/);
assert.match(workspaceSource, /const activeTarget = state\.ink\.activeTarget;[\s\S]*?activeTarget\.kind === "student_card"[\s\S]*?setInkCommand\(\{[\s\S]*?target: activeTarget[\s\S]*?action: "clear"/);
assert.match(workspaceSource, /activeTarget\.kind === "private_board"[\s\S]*?dispatch\(\{ type: "clear_active_ink" \}\)/);
assert.match(workspaceSource, /state\.ink\.activeTarget\.kind === "student_card"\s*\|\|[\s\S]*?state\.ink\.activeTarget\.kind === "private_board"[\s\S]*?state\.privateBoardStrokes\.length > 0/);
assert.doesNotMatch(workspaceSource, /target: "student_card"/);
assert.match(workspaceSource, /<BoardInkToolbar[\s\S]*?tool=\{state\.ink\.tool\}[\s\S]*?color=\{state\.ink\.color\}[\s\S]*?canUndo=\{canChangeActiveInk\}[\s\S]*?canClear=\{canChangeActiveInk\}[\s\S]*?onToolChange=\{setInkTool\}[\s\S]*?onColorChange=\{setInkColor\}[\s\S]*?onUndo=\{undoActiveInk\}[\s\S]*?onClear=\{clearActiveInk\}/);
assert.ok(workspaceSource.indexOf("<BoardInkToolbar") < workspaceSource.indexOf("<CanvasViewport"));
assert.match(workspaceSource, /<PrivateBoardInkLayer[\s\S]*?strokes=\{state\.privateBoardStrokes\}[\s\S]*?tool=\{state\.ink\.tool\}[\s\S]*?color=\{state\.ink\.color\}[\s\S]*?onCommitStroke=\{commitPrivateBoardStroke\}/);
assert.ok(workspaceSource.indexOf("<PrivateBoardInkLayer") < workspaceSource.indexOf("<TutorObjectLayer"));
assert.ok(workspaceSource.indexOf("<PrivateBoardInkLayer") < workspaceSource.indexOf("<StickyNoteLayer"));
assert.ok(workspaceSource.indexOf("<PrivateBoardInkLayer") < workspaceSource.indexOf("state.studentCards.map"));

const boardInkToolbarPath = new URL("../src/components/session/BoardInkToolbar.tsx", import.meta.url);
const boardInkToolbarSource = fs.readFileSync(boardInkToolbarPath, "utf8");
assert.match(boardInkToolbarSource, /"#213f35"/);
assert.match(boardInkToolbarSource, /"#ff775f"/);
assert.match(boardInkToolbarSource, /"#2f6fed"/);
assert.match(boardInkToolbarSource, /"#7c4dff"/);
assert.match(boardInkToolbarSource, /Pencil/);
assert.match(boardInkToolbarSource, /Eraser/);
assert.match(boardInkToolbarSource, /Undo2/);
assert.match(boardInkToolbarSource, /Trash2/);
assert.match(boardInkToolbarSource, /ink-color-swatch/);
assert.doesNotMatch(boardInkToolbarSource, /USER_BOARD_TOPIC/);
assert.doesNotMatch(boardInkToolbarSource, /useBoardChannel/);
assert.doesNotMatch(boardInkToolbarSource, /whiteboard/);

const handwritingPanelPath = new URL("../src/components/session/HandwritingPanel.tsx", import.meta.url);
const handwritingPanelSource = fs.readFileSync(handwritingPanelPath, "utf8");
assert.match(handwritingPanelSource, /inkTool/);
assert.match(handwritingPanelSource, /inkColor/);
assert.match(handwritingPanelSource, /inkCommand/);
assert.match(handwritingPanelSource, /onStrokeTargeted/);
assert.match(handwritingPanelSource, /getCoalescedEvents/);
assert.match(handwritingPanelSource, /target:\s*Extract<InkTarget,\s*\{ kind: "student_card" \}>/);
assert.match(handwritingPanelSource, /inkCommand\.target\.kind !== "student_card"/);
assert.match(handwritingPanelSource, /inkCommand\.target\.cardId !== cardId/);
assert.match(handwritingPanelSource, /if \(strokesRef\.current\.length === 0\) return;/);
assert.match(handwritingPanelSource, /releasePointerCapture\(e\.pointerId\)/);
assert.match(handwritingPanelSource, /onLostPointerCapture=\{\(\) => \{\s*dragRef\.current = null;\s*\}\}/);
assert.match(handwritingPanelSource, /onLostPointerCapture=\{\(\) => \{\s*resizeRef\.current = null;\s*\}\}/);
assert.doesNotMatch(handwritingPanelSource, /import\s*\{[^}]*\b(?:Eraser|Pencil|Trash2|Undo2)\b[^}]*\}\s*from "lucide-react"/);
assert.doesNotMatch(handwritingPanelSource, /aria-label="Pen"/);
assert.doesNotMatch(handwritingPanelSource, /aria-label="Eraser"/);
assert.doesNotMatch(handwritingPanelSource, /aria-label="Undo"/);
assert.doesNotMatch(handwritingPanelSource, /aria-label="Clear"/);
assert.match(handwritingPanelSource, /USER_BOARD_TOPIC/);
assert.match(handwritingPanelSource, /useBoardChannel/);
assert.match(handwritingPanelSource, /card_label:\s*label/);
assert.match(handwritingPanelSource, /card_id:\s*cardId/);
assert.match(handwritingPanelSource, /onRename/);
assert.match(handwritingPanelSource, /handwriting-topic-input/);
assert.match(handwritingPanelSource, /GripVertical/);
assert.match(handwritingPanelSource, /handwriting-drag-grip/);
assert.match(handwritingPanelSource, /draftLabel/);
assert.match(handwritingPanelSource, /onBlur=\{\(\) => onRename\(cardId, draftLabel\)\}/);
assert.match(handwritingPanelSource, /aria-label="Student card topic"/);
assert.match(workspaceSource, /renameStudentCard/);
assert.match(workspaceSource, /onRename=\{renameStudentCard\}/);
assert.match(workspaceSource, /inkTool=\{state\.ink\.tool\}/);
assert.match(workspaceSource, /inkColor=\{state\.ink\.color\}/);
assert.match(workspaceSource, /inkCommand=\{inkCommand\}/);
assert.match(workspaceSource, /onStrokeTargeted=\{setActiveInkTarget\}/);
assert.match(workspaceSource, /import StickyNoteLayer from "\.\/StickyNoteLayer"/);
assert.match(workspaceSource, /<StickyNoteLayer[\s\S]*?notes=\{state\.stickyNotes\}[\s\S]*?onMoveNote=\{moveStickyNote\}[\s\S]*?onResizeNote=\{resizeStickyNote\}[\s\S]*?onTextChange=\{updateStickyNoteText\}/);
assert.match(workspaceSource, /StickyNote(?:\s+as\s+StickyNoteIcon)?/);
assert.match(workspaceSource, /const addStickyNote = useCallback/);
assert.match(workspaceSource, /dispatch\(\{[\s\S]*?type: "add_sticky_note"[\s\S]*?boardSize: getBoardSize\(\)[\s\S]*?\}\)/);
assert.match(workspaceSource, /aria-label="Add sticky note"/);

const stickyNoteLayerPath = new URL("../src/components/session/StickyNoteLayer.tsx", import.meta.url);
const stickyNoteLayerSource = fs.readFileSync(stickyNoteLayerPath, "utf8");
assert.match(stickyNoteLayerSource, /notes\.map/);
assert.match(stickyNoteLayerSource, /clientToWorld/);
assert.match(stickyNoteLayerSource, /viewport\.zoom/);
assert.match(stickyNoteLayerSource, /sticky-note-text/);
assert.match(stickyNoteLayerSource, /onMoveNote/);
assert.match(stickyNoteLayerSource, /onResizeNote/);
assert.match(stickyNoteLayerSource, /onTextChange/);
assert.match(stickyNoteLayerSource, /onPointerDown=\{\(event\) => event\.stopPropagation\(\)\}/);
assert.match(stickyNoteLayerSource, /onKeyDown=\{\(event\) => resizeWithKeyboard\(event, note\)\}/);
assert.match(stickyNoteLayerSource, /ArrowRight/);
assert.match(stickyNoteLayerSource, /ArrowLeft/);
assert.match(stickyNoteLayerSource, /ArrowDown/);
assert.match(stickyNoteLayerSource, /ArrowUp/);
assert.doesNotMatch(stickyNoteLayerSource, /USER_BOARD_TOPIC/);
assert.doesNotMatch(stickyNoteLayerSource, /useBoardChannel/);
assert.doesNotMatch(stickyNoteLayerSource, /whiteboard/);

const privateBoardInkLayerPath = new URL("../src/components/session/PrivateBoardInkLayer.tsx", import.meta.url);
const privateBoardInkLayerSource = fs.readFileSync(privateBoardInkLayerPath, "utf8");
assert.match(privateBoardInkLayerSource, /strokes:\s*PrivateBoardInkStroke\[\]/);
assert.match(privateBoardInkLayerSource, /tool:\s*InkTool/);
assert.match(privateBoardInkLayerSource, /color:\s*InkColor/);
assert.match(privateBoardInkLayerSource, /onCommitStroke:\s*\(stroke:\s*PrivateBoardInkStroke\) => void/);
assert.match(privateBoardInkLayerSource, /getCoalescedEvents/);
assert.match(privateBoardInkLayerSource, /getStroke/);
assert.match(privateBoardInkLayerSource, /clientToWorld/);
assert.match(privateBoardInkLayerSource, /isSpacePan/);
assert.match(privateBoardInkLayerSource, /event\.button !== 0 \|\| isSpacePan \|\| activePointerRef\.current !== null/);
assert.match(privateBoardInkLayerSource, /blurActiveEditable\(\);[\s\S]*?event\.preventDefault\(\)/);
assert.match(privateBoardInkLayerSource, /function blurActiveEditable\(\)/);
assert.match(privateBoardInkLayerSource, /activeElement\.blur\(\)/);
assert.match(privateBoardInkLayerSource, /setPointerCapture/);
assert.match(privateBoardInkLayerSource, /releasePointerCapture/);
assert.match(privateBoardInkLayerSource, /draftStrokeRef/);
assert.doesNotMatch(privateBoardInkLayerSource, /onCommitStroke\(stroke\);[\s\S]*?return null;/);
assert.match(privateBoardInkLayerSource, /completedStroke\.points\.length > 1/);
assert.match(privateBoardInkLayerSource, /viewBox=\{`\$\{WORLD_ORIGIN\} \$\{WORLD_ORIGIN\} \$\{WORLD_SIZE\} \$\{WORLD_SIZE\}`\}/);
assert.match(privateBoardInkLayerSource, /committedPaths = useMemo/);
assert.match(privateBoardInkLayerSource, /draftPath = useMemo/);
assert.match(privateBoardInkLayerSource, /<mask id=\{maskId\}/);
assert.match(privateBoardInkLayerSource, /stroke\.tool === "eraser"/);
assert.match(privateBoardInkLayerSource, /strokeToPath/);
assert.match(privateBoardInkLayerSource, /private-board-ink-layer/);
assert.match(privateBoardInkLayerSource, /private-board-ink-svg/);
assert.doesNotMatch(privateBoardInkLayerSource, /USER_BOARD_TOPIC/);
assert.doesNotMatch(privateBoardInkLayerSource, /useBoardChannel/);
assert.doesNotMatch(privateBoardInkLayerSource, /whiteboard/);

const sessionCssPath = new URL("../src/styles/session.css", import.meta.url);
const sessionCss = fs.readFileSync(sessionCssPath, "utf8");
assert.match(sessionCss, /\.board-top-actions\s*\{[^}]*display:\s*grid;/s);
assert.match(sessionCss, /\.board-top-actions\s*\{[^}]*gap:\s*8px;/s);
assert.match(sessionCss, /\.board-top-actions\s*\{[^}]*--board-tool-rail-width:\s*38px;/s);
assert.match(sessionCss, /\.board-top-actions button\s*\{[^}]*width:\s*var\(--board-tool-rail-width\);[^}]*height:\s*var\(--board-tool-rail-width\);/s);
assert.match(sessionCss, /\.private-board-ink-layer\s*\{/s);
assert.match(sessionCss, /\.private-board-ink-layer\s*\{[^}]*left:\s*-10000px;[^}]*top:\s*-10000px;[^}]*width:\s*20000px;[^}]*height:\s*20000px;/s);
assert.match(sessionCss, /\.private-board-ink-svg\s*\{/s);
assert.match(sessionCss, /\.sticky-note-layer\s*\{/s);
assert.match(sessionCss, /\.sticky-note\s*\{/s);
assert.match(sessionCss, /\.sticky-note-handle\s*\{/s);
assert.match(sessionCss, /\.sticky-note-text\s*\{/s);
assert.match(sessionCss, /\.sticky-note-text:focus-visible\s*\{/s);
assert.match(sessionCss, /\.sticky-note-resize\s*\{/s);
assert.match(sessionCss, /\.tutor-object\s*\{[^}]*position:\s*absolute;/s);
assert.doesNotMatch(sessionCss, /\.tutor-object-collapsed\s*\{[^}]*cursor:\s*pointer;/s);
assert.match(sessionCss, /\.tutor-object-collapsed\s+\.tutor-object-handle\s*\{[^}]*cursor:\s*grab;/s);
assert.match(sessionCss, /\.tutor-object-title-html\s*\{[^}]*overflow:\s*hidden;/s);
assert.match(sessionCss, /\.tutor-object-title-actions\s*\{[^}]*display:\s*inline-flex;/s);
assert.match(sessionCss, /\.tutor-object-title-action\s*\{[^}]*touch-action:\s*manipulation;/s);
assert.match(sessionCss, /\.tutor-object-resize\s*\{[^}]*cursor:\s*nwse-resize;/s);
assert.match(sessionCss, /\.handwriting-drag-grip\s*\{[^}]*cursor:\s*grab;/s);
assert.match(sessionCss, /\.handwriting-topic-input\s*\{[^}]*cursor:\s*text;/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*--board-tool-rail-width:\s*38px;/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*top:\s*170px;/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*right:\s*14px;/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*flex-direction:\s*column;/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*flex-wrap:\s*nowrap;/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*width:\s*var\(--board-tool-rail-width\);/s);
assert.match(sessionCss, /\.board-ink-toolbar\s*\{[^}]*max-height:\s*calc\(100% - 184px\);/s);
assert.match(sessionCss, /\.board-ink-toolbar button\.active\s*\{[^}]*background:\s*rgba\(41,\s*72,\s*62,\s*0\.1\);[^}]*color:\s*var\(--mb-green\);/s);
assert.match(sessionCss, /\.board-ink-divider\s*\{[^}]*width:\s*22px;[^}]*height:\s*1px;/s);
assert.match(sessionCss, /\.ink-color-swatch\s*\{/s);
assert.doesNotMatch(sessionCss, /\.tutor-focus-rail/s);
assert.doesNotMatch(sessionCss, /\.tutor-object-history/s);
assert.doesNotMatch(sessionCss, /\.tutor-object-(?:plot|shape|diagram)\s*\{[^}]*(?:width|min-height)\s*:/s);
