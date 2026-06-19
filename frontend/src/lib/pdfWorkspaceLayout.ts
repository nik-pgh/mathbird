export type TextbookState = "large" | "small";
export type TextbookDisplayMode = "hidden" | "collapsed" | "docked" | "overlay";

export const PDF_DOCK_BREAKPOINT = 720;
export const PDF_DOCK_MIN_WIDTH = 280;
export const PDF_DOCK_MAX_WIDTH = 420;
export const PDF_DOCK_WIDTH_RATIO = 0.34;

export function textbookDisplayMode({
  hasDocument,
  textbook,
  workspaceWidth,
}: {
  hasDocument: boolean;
  textbook: TextbookState;
  workspaceWidth: number;
}): TextbookDisplayMode {
  if (!hasDocument) return "hidden";
  if (textbook === "small") return "collapsed";
  return workspaceWidth >= PDF_DOCK_BREAKPOINT ? "docked" : "overlay";
}

export function pdfDockWidth(workspaceWidth: number): number {
  const proportionalWidth = Math.round(workspaceWidth * PDF_DOCK_WIDTH_RATIO);
  return Math.max(
    PDF_DOCK_MIN_WIDTH,
    Math.min(PDF_DOCK_MAX_WIDTH, proportionalWidth),
  );
}
