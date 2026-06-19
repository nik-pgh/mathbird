export type TextbookState = "large" | "small";
export type TextbookDisplayMode = "hidden" | "collapsed" | "docked" | "overlay";

export const PDF_DOCK_BREAKPOINT = 720;
export const PDF_DOCK_MIN_WIDTH = 280;
export const PDF_DOCK_MIN_BOARD_WIDTH = 320;
export const PDF_DOCK_WIDTH_RATIO = 0.34;
export const PDF_DOCK_MAX_WIDTH_RATIO = 0.72;
export const PDF_DOCK_PAGE_ASPECT_RATIO = 8.5 / 11;

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

export function pdfDockWidth(
  workspaceWidth: number,
  workspaceHeight: number,
): number {
  const proportionalWidth = Math.round(workspaceWidth * PDF_DOCK_WIDTH_RATIO);
  const heightFillWidth =
    workspaceHeight > 0
      ? Math.round(workspaceHeight * PDF_DOCK_PAGE_ASPECT_RATIO)
      : proportionalWidth;
  const maxWidth = Math.max(
    PDF_DOCK_MIN_WIDTH,
    Math.min(
      Math.floor(workspaceWidth * PDF_DOCK_MAX_WIDTH_RATIO),
      Math.max(PDF_DOCK_MIN_WIDTH, workspaceWidth - PDF_DOCK_MIN_BOARD_WIDTH),
    ),
  );

  return Math.max(
    PDF_DOCK_MIN_WIDTH,
    Math.min(maxWidth, Math.max(proportionalWidth, heightFillWidth)),
  );
}
