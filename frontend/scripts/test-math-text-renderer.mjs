import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import katex from "katex";

const sourcePath = new URL("../src/lib/mathText.ts", import.meta.url);
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
  require(name) {
    if (name === "katex") return { __esModule: true, default: katex };
    throw new Error(`Unexpected require: ${name}`);
  },
};

vm.runInNewContext(compiled, sandbox, { filename: "mathText.ts" });

const { renderMathTextToHtml } = sandbox.exports;

assert.equal(typeof renderMathTextToHtml, "function");

const inline = renderMathTextToHtml("Given \\(2^4 = 2^x\\), solve for x.");
assert.match(inline, /katex/);
assert.doesNotMatch(inline, /\\\(2\^4/);
assert.match(inline, /solve for x\./);

const display = renderMathTextToHtml("Factor:\n\\[24 = 2 \\times 2 \\times 2 \\times 3\\]");
assert.match(display, /katex-display/);
assert.doesNotMatch(display, /\\\[24/);
assert.match(display, /Factor:<br\/>/);

const compact = renderMathTextToHtml("One paragraph.\n\nNext paragraph with \\(2^4\\).", {
  lineBreaks: "collapse",
});
assert.doesNotMatch(compact, /<br\/>/);
assert.match(compact, /One paragraph\. Next paragraph with/);
assert.match(compact, /katex/);

const spacedInline = renderMathTextToHtml("So for \\(54\\), we have \\(2 \\times 3^3\\).", {
  lineBreaks: "collapse",
});
assert.match(spacedInline, /So for <span class="katex"/);
assert.doesNotMatch(spacedInline, /for<span class="katex"/);

const bareBreaks = renderMathTextToHtml("Prime factorization of 54 \\ 54=2×27 \\ 27=3×9");
assert.match(bareBreaks, /Prime factorization of 54 <br\/> 54=2×27 <br\/> 27=3×9/);
assert.doesNotMatch(bareBreaks, / \\ 54=/);

const attachedBareBreaks = renderMathTextToHtml(
  "Divisors of 42\\ Since 42 is an even number, it is definitely divisible by 2.",
);
assert.match(
  attachedBareBreaks,
  /Divisors of 42<br\/> Since 42 is an even number/,
);
assert.doesNotMatch(attachedBareBreaks, /42\\ Since/);

const escapedNewlines = renderMathTextToHtml(
  "Factors of 42\\n\\nFinding the prime factorization will help.",
);
assert.match(
  escapedNewlines,
  /Factors of 42<br\/><br\/>Finding the prime factorization will help\./,
);
assert.doesNotMatch(escapedNewlines, /\\n/);

const escaped = renderMathTextToHtml("<script>alert(1)</script> $2^3$");
assert.doesNotMatch(escaped, /<script>/);
assert.match(escaped, /&lt;script&gt;/);
assert.match(escaped, /katex/);
