/** US Letter portrait page (8.5 × 11 in). */
export const PDF_PAGE_ASPECT = 11 / 8.5;

export const TEXTBOOK_HEAD_HEIGHT = 42;

export function textbookLargeHeight(width: number): number {
  return TEXTBOOK_HEAD_HEIGHT + width * PDF_PAGE_ASPECT;
}

export function textbookLargeWidth(boardWidth: number, boardHeight: number): number {
  const widthCap =
    boardWidth <= 900
      ? Math.min(380, boardWidth - 24)
      : Math.min(430, boardWidth * 0.38);

  if (boardHeight <= 0) return widthCap;

  const maxWidthFromHeight =
    (boardHeight - 160 - TEXTBOOK_HEAD_HEIGHT) / PDF_PAGE_ASPECT;

  return Math.min(widthCap, maxWidthFromHeight);
}

export function textbookLargeClearance(
  boardWidth: number,
  boardHeight: number,
): number {
  const width = textbookLargeWidth(boardWidth, boardHeight);
  return textbookLargeHeight(width);
}
