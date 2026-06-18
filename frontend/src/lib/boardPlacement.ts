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
