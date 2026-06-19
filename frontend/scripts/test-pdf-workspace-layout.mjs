import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const sourcePath = new URL("../src/lib/pdfWorkspaceLayout.ts", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

const sandbox = { exports: {} };
vm.runInNewContext(compiled, sandbox, { filename: "pdfWorkspaceLayout.ts" });

const {
  PDF_DOCK_BREAKPOINT,
  PDF_DOCK_MAX_WIDTH_RATIO,
  PDF_DOCK_MIN_BOARD_WIDTH,
  PDF_DOCK_MIN_WIDTH,
  PDF_DOCK_PAGE_ASPECT_RATIO,
  pdfDockWidth,
  textbookDisplayMode,
} = sandbox.exports;

assert.equal(PDF_DOCK_BREAKPOINT, 720);
assert.equal(PDF_DOCK_MIN_WIDTH, 280);
assert.equal(PDF_DOCK_MIN_BOARD_WIDTH, 320);
assert.equal(PDF_DOCK_MAX_WIDTH_RATIO, 0.72);
assert.equal(PDF_DOCK_PAGE_ASPECT_RATIO, 8.5 / 11);

assert.equal(textbookDisplayMode({ hasDocument: false, textbook: "small", workspaceWidth: 1200 }), "hidden");
assert.equal(textbookDisplayMode({ hasDocument: true, textbook: "small", workspaceWidth: 1200 }), "collapsed");
assert.equal(textbookDisplayMode({ hasDocument: true, textbook: "large", workspaceWidth: 390 }), "overlay");
assert.equal(textbookDisplayMode({ hasDocument: true, textbook: "large", workspaceWidth: 719 }), "overlay");
assert.equal(textbookDisplayMode({ hasDocument: true, textbook: "large", workspaceWidth: 720 }), "docked");
assert.equal(textbookDisplayMode({ hasDocument: true, textbook: "large", workspaceWidth: 1024 }), "docked");

assert.equal(pdfDockWidth(390, 500), 280);
assert.equal(pdfDockWidth(720, 600), 400);
assert.equal(pdfDockWidth(1024, 640), 495);
assert.equal(pdfDockWidth(1600, 900), 695);
assert.equal(pdfDockWidth(900, 1200), 580);
