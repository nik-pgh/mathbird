export interface BoardRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BoardSize {
  width: number;
  height: number;
}

export type VisualKind = "text" | "plot" | "shape" | "diagram";

const PLACEMENT_GAP = 14;
const FALLBACK_EXPANSION_STEPS = 20;

export function rectsOverlap(a: BoardRect, b: BoardRect, gap = 14): boolean {
  return !(
    a.x + a.width + gap <= b.x
    || b.x + b.width + gap <= a.x
    || a.y + a.height + gap <= b.y
    || b.y + b.height + gap <= a.y
  );
}

export function tutorCardSizeForKind(kind: VisualKind): BoardSize {
  if (kind === "plot") return { width: 360, height: 250 };
  if (kind === "shape") return { width: 340, height: 240 };
  if (kind === "diagram") return { width: 380, height: 260 };
  return { width: 340, height: 180 };
}

export const TUTOR_FLOW_COLUMN_GAP = 24;
export const TUTOR_FLOW_ROW_GAP = 10;
export const COLLAPSED_TUTOR_RIBBON_HEIGHT = 44;
export const TUTOR_FLOW_MIN_COLUMN_HEIGHT = 520;

export interface TutorFlowItem {
  id: string;
  collapsed?: boolean;
  size: BoardSize;
}

export interface TutorFlowLayout {
  positions: Record<string, { x: number; y: number }>;
  width: number;
  height: number;
}

export function clampTutorCardSize(size: BoardSize): BoardSize {
  return {
    width: Math.max(280, Math.min(720, size.width)),
    height: Math.max(180, Math.min(520, size.height)),
  };
}

export function tutorFlowMaxColumnHeight(boardHeight: number, padding = 72): number {
  return Math.max(TUTOR_FLOW_MIN_COLUMN_HEIGHT, boardHeight - padding);
}

export function tutorFlowItemHeight(item: TutorFlowItem): number {
  return item.collapsed ? COLLAPSED_TUTOR_RIBBON_HEIGHT : item.size.height;
}

export function layoutTutorFlow({
  origin,
  items,
  maxColumnHeight,
}: {
  origin: { x: number; y: number };
  items: TutorFlowItem[];
  maxColumnHeight: number;
}): TutorFlowLayout {
  const positions: Record<string, { x: number; y: number }> = {};
  let x = origin.x;
  let y = origin.y;
  let columnWidth = 0;
  let flowWidth = 0;
  let flowHeight = 0;

  for (const item of items) {
    const itemHeight = tutorFlowItemHeight(item);
    if (
      y > origin.y
      && y + itemHeight > origin.y + maxColumnHeight
    ) {
      x += columnWidth + TUTOR_FLOW_COLUMN_GAP;
      y = origin.y;
      columnWidth = 0;
    }

    positions[item.id] = { x, y };
    columnWidth = Math.max(columnWidth, item.size.width);
    flowWidth = Math.max(flowWidth, x + item.size.width - origin.x);
    flowHeight = Math.max(flowHeight, y + itemHeight - origin.y);
    y += itemHeight + TUTOR_FLOW_ROW_GAP;
  }

  return { positions, width: flowWidth, height: flowHeight };
}

export function deriveTutorBoardTitle(
  item: { kind: VisualKind; id: string; label?: string | null; markdown?: string },
  index: number,
): string {
  const label = "label" in item ? item.label?.trim() : "";
  if (label) return label;

  if (item.kind === "text" && "markdown" in item) {
    const line = item.markdown
      .split(/\r?\n/)
      .map((part) => part.replace(/^#+\s*/, "").trim())
      .find(Boolean);
    if (line) return line.slice(0, 48);
  }

  if (item.kind === "shape") return `Sketch ${index}`;
  return `Tutor Board ${index}`;
}

export function findOpenBoardPosition({
  size,
  occupied,
  viewport,
  margin = 36,
}: {
  size: BoardSize;
  occupied: BoardRect[];
  viewport: BoardRect;
  margin?: number;
}): { x: number; y: number } {
  const stepX = size.width + 28;
  const stepY = size.height + 28;
  const maxX = Math.max(
    viewport.x + margin,
    viewport.x + viewport.width - size.width - margin,
  );
  const maxY = Math.max(
    viewport.y + margin,
    viewport.y + viewport.height - size.height - margin,
  );

  for (let y = viewport.y + margin; y <= maxY; y += stepY) {
    for (let x = viewport.x + margin; x <= maxX; x += stepX) {
      const candidate = { x, y, width: size.width, height: size.height };
      if (isOpen(candidate, occupied)) {
        return { x, y };
      }
    }
  }

  const expandedMaxX = maxX + stepX * FALLBACK_EXPANSION_STEPS;
  const expandedMaxY = maxY + stepY * FALLBACK_EXPANSION_STEPS;
  for (let y = viewport.y + margin; y <= expandedMaxY; y += stepY) {
    for (let x = viewport.x + margin; x <= expandedMaxX; x += stepX) {
      const candidate = { x, y, width: size.width, height: size.height };
      if (isOpen(candidate, occupied)) {
        return { x, y };
      }
    }
  }

  const occupiedRight = occupied.reduce(
    (right, rect) => Math.max(right, rect.x + rect.width),
    viewport.x + margin,
  );
  return {
    x: occupiedRight + PLACEMENT_GAP,
    y: viewport.y + margin,
  };
}

function isOpen(candidate: BoardRect, occupied: BoardRect[]): boolean {
  return !occupied.some((rect) => rectsOverlap(candidate, rect));
}
