import katex from "katex";

type MathToken =
  | { kind: "text"; value: string }
  | { kind: "math"; value: string; displayMode: boolean };

interface RenderMathTextOptions {
  lineBreaks?: "preserve" | "collapse";
}

export function renderMathTextToHtml(
  src: string,
  options: RenderMathTextOptions = {},
): string {
  const lineBreaks = options.lineBreaks ?? "preserve";
  return tokenizeMath(src)
    .map((token) => {
      if (token.kind === "text") {
        return applyInlineMarkdown(escapeHtml(token.value), lineBreaks);
      }
      try {
        return katex.renderToString(token.value, {
          throwOnError: false,
          output: "html",
          displayMode: token.displayMode,
        });
      } catch {
        return `<code>${escapeHtml(token.value)}</code>`;
      }
    })
    .join("");
}

function tokenizeMath(src: string): MathToken[] {
  const tokens: MathToken[] = [];
  let textStart = 0;
  let i = 0;

  while (i < src.length) {
    const delimiter = readOpeningDelimiter(src, i);
    if (!delimiter) {
      i += 1;
      continue;
    }

    const close = src.indexOf(delimiter.close, i + delimiter.open.length);
    if (close === -1) {
      i += delimiter.open.length;
      continue;
    }

    if (textStart < i) {
      tokens.push({ kind: "text", value: src.slice(textStart, i) });
    }
    tokens.push({
      kind: "math",
      value: src.slice(i + delimiter.open.length, close),
      displayMode: delimiter.displayMode,
    });
    i = close + delimiter.close.length;
    textStart = i;
  }

  if (textStart < src.length) {
    tokens.push({ kind: "text", value: src.slice(textStart) });
  }

  return tokens;
}

function readOpeningDelimiter(
  src: string,
  index: number,
): { open: string; close: string; displayMode: boolean } | null {
  if (src.startsWith("\\[", index)) {
    return { open: "\\[", close: "\\]", displayMode: true };
  }
  if (src.startsWith("\\(", index)) {
    return { open: "\\(", close: "\\)", displayMode: false };
  }
  if (src.startsWith("$$", index)) {
    return { open: "$$", close: "$$", displayMode: true };
  }
  if (src[index] === "$") {
    return { open: "$", close: "$", displayMode: false };
  }
  return null;
}

function applyInlineMarkdown(
  src: string,
  lineBreaks: "preserve" | "collapse",
): string {
  if (lineBreaks === "collapse") {
    return applyEmphasisAndCode(src.replace(/\s+/g, " "));
  }
  return applyEmphasisAndCode(
    src
      .replace(/\\\\/g, "<br/>")
      .replace(/(^|\s)\\(?=\s|$)/g, "$1<br/>")
      .replace(/\n/g, "<br/>"),
  );
}

function applyEmphasisAndCode(src: string): string {
  return src
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>")
    .replace(/(?<!_)_([^_\n]+)_(?!_)/g, "<em>$1</em>")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
