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

export interface ViewportLike {
  pan: { x: number; y: number };
  zoom: number;
}

export interface GridOccupant {
  id: string;
  position: { x: number; y: number };
  size?: BoardSize;
  kind?: VisualKind;
}

export interface GridOccupantSnapshot {
  id: string;
  position: { x: number; y: number };
  size: BoardSize;
}

export interface GridMovePreview {
  landing: { x: number; y: number };
  willPush: boolean;
  canPlace: boolean;
}

const FALLBACK_EXPANSION_STEPS = 20;
const PUSH_SEARCH_STEPS = 48;

/** 5 × 18px dot grid — finer snap than the old 180px cells. */
export const GRID_CELL_SIZE = 90;
export const GRID_MIN_SPAN = 1;
export const GRID_MAX_SPAN = 8;

export const COLLAPSED_TUTOR_RIBBON_HEIGHT = 44;

export function tutorCardSizeForKind(kind: VisualKind): BoardSize {
  if (kind === "plot") return { width: 360, height: 250 };
  if (kind === "shape") return { width: 340, height: 240 };
  if (kind === "diagram") return { width: 380, height: 260 };
  return { width: 340, height: 180 };
}

export function clampTutorCardSize(size: BoardSize): BoardSize {
  return {
    width: Math.max(270, Math.min(720, size.width)),
    height: Math.max(180, Math.min(520, size.height)),
  };
}

function roundToNearestCell(value: number): number {
  return Math.round(value / GRID_CELL_SIZE) * GRID_CELL_SIZE;
}

const STUDENT_CARD_ASPECT = 0.75;
const STUDENT_CARD_MIN_WIDTH = 270;
const STUDENT_CARD_MAX_WIDTH = 720;
const STUDENT_CARD_MAX_HEIGHT = 540;
const STICKY_NOTE_MIN_SIZE = 90;
const STICKY_NOTE_MAX_SIZE = 360;

export function studentCardDefaultSize(): BoardSize {
  return { width: 360, height: 270 };
}

export function stickyNoteDefaultSize(): BoardSize {
  return { width: 180, height: 180 };
}

export function gridKeyboardResizeStep(event: { altKey: boolean; shiftKey: boolean }): number {
  if (event.altKey) return GRID_CELL_SIZE / 2;
  if (event.shiftKey) return GRID_CELL_SIZE * 2;
  return GRID_CELL_SIZE;
}

export function clampStudentCardSize(size: BoardSize): BoardSize {
  const aspectWidth = Math.max(size.width, size.height / STUDENT_CARD_ASPECT);
  let width = Math.max(
    STUDENT_CARD_MIN_WIDTH,
    Math.min(STUDENT_CARD_MAX_WIDTH, aspectWidth),
  );
  width = roundToNearestCell(width);

  let height = roundToNearestCell(width * STUDENT_CARD_ASPECT);
  height = Math.max(GRID_CELL_SIZE * 2, Math.min(STUDENT_CARD_MAX_HEIGHT, height));

  return { width, height };
}

export function clampStickyNoteSize(size: BoardSize): BoardSize {
  const side = roundToNearestCell(Math.max(size.width, size.height));
  const clamped = Math.max(STICKY_NOTE_MIN_SIZE, Math.min(STICKY_NOTE_MAX_SIZE, side));
  return { width: clamped, height: clamped };
}

export function worldToCell(x: number, y: number): { col: number; row: number } {
  return {
    col: Math.floor(x / GRID_CELL_SIZE),
    row: Math.floor(y / GRID_CELL_SIZE),
  };
}

export function cellToWorld(col: number, row: number): { x: number; y: number } {
  return {
    x: col * GRID_CELL_SIZE,
    y: row * GRID_CELL_SIZE,
  };
}

export function snapPositionToGrid(position: { x: number; y: number }): { x: number; y: number } {
  const { col, row } = worldToCell(position.x, position.y);
  return cellToWorld(col, row);
}

export function snapPositionToNearestGrid(position: { x: number; y: number }): { x: number; y: number } {
  const col = Math.round(position.x / GRID_CELL_SIZE);
  const row = Math.round(position.y / GRID_CELL_SIZE);
  return cellToWorld(Math.max(0, col), Math.max(0, row));
}

export function spanForSize(size: BoardSize): { cols: number; rows: number } {
  const cols = Math.ceil(size.width / GRID_CELL_SIZE);
  const rows = Math.ceil(size.height / GRID_CELL_SIZE);
  return {
    cols: Math.min(GRID_MAX_SPAN, Math.max(GRID_MIN_SPAN, cols)),
    rows: Math.min(GRID_MAX_SPAN, Math.max(GRID_MIN_SPAN, rows)),
  };
}

export function clampToCellSpan(size: BoardSize): BoardSize {
  const clamped = clampTutorCardSize({
    width: roundToNearestCell(size.width),
    height: roundToNearestCell(size.height),
  });
  return {
    width: Math.max(GRID_CELL_SIZE * 3, roundToNearestCell(clamped.width)),
    height: Math.max(GRID_CELL_SIZE * 2, roundToNearestCell(clamped.height)),
  };
}

function cellKey(col: number, row: number): string {
  return `${col},${row}`;
}

function occupantRect(
  position: { x: number; y: number },
  size: BoardSize,
): BoardRect {
  return {
    x: position.x,
    y: position.y,
    width: size.width,
    height: size.height,
  };
}

/** Mark every grid cell the pixel rect intersects — not just from floored origin + span. */
function cellsForRect(rect: BoardRect): Set<string> {
  const cells = new Set<string>();
  if (rect.width <= 0 || rect.height <= 0) return cells;

  const colMin = Math.floor(rect.x / GRID_CELL_SIZE);
  const colMax = Math.floor((rect.x + rect.width - 1) / GRID_CELL_SIZE);
  const rowMin = Math.floor(rect.y / GRID_CELL_SIZE);
  const rowMax = Math.floor((rect.y + rect.height - 1) / GRID_CELL_SIZE);

  for (let col = colMin; col <= colMax; col += 1) {
    for (let row = rowMin; row <= rowMax; row += 1) {
      cells.add(cellKey(col, row));
    }
  }
  return cells;
}

function markRectOnGrid(occupied: Set<string>, rect: BoardRect): void {
  for (const cell of cellsForRect(rect)) {
    occupied.add(cell);
  }
}

function rectIsFree(rect: BoardRect, occupied: Set<string>): boolean {
  for (const cell of cellsForRect(rect)) {
    if (occupied.has(cell)) return false;
  }
  return true;
}

function rectsOverlap(a: BoardRect, b: BoardRect): boolean {
  return (
    a.x < b.x + b.width
    && a.x + a.width > b.x
    && a.y < b.y + b.height
    && a.y + a.height > b.y
  );
}

export function rectCollidesWithOccupied(rect: BoardRect, occupied: Set<string>): boolean {
  for (const cell of cellsForRect(rect)) {
    if (occupied.has(cell)) return true;
  }
  return false;
}

function markOccupantOnGrid(
  occupied: Set<string>,
  occupant: GridOccupant,
  defaultSize: BoardSize,
): void {
  const size = occupant.size ?? defaultSize;
  markRectOnGrid(occupied, occupantRect(occupant.position, size));
}

export function occupiedCells(
  objects: GridOccupant[],
  studentCards: GridOccupant[],
  stickyNotes: GridOccupant[],
  excludeId?: string,
): Set<string> {
  const occupied = new Set<string>();
  for (const occupant of objects) {
    if (excludeId && occupant.id === excludeId) continue;
    const size = occupant.size ?? (occupant.kind
      ? tutorCardSizeForKind(occupant.kind)
      : tutorCardSizeForKind("text"));
    markRectOnGrid(occupied, occupantRect(occupant.position, size));
  }
  for (const occupant of studentCards) {
    if (excludeId && occupant.id === excludeId) continue;
    markOccupantOnGrid(occupied, occupant, studentCardDefaultSize());
  }
  for (const occupant of stickyNotes) {
    if (excludeId && occupant.id === excludeId) continue;
    markOccupantOnGrid(occupied, occupant, stickyNoteDefaultSize());
  }
  return occupied;
}

export function addRectToOccupied(
  occupied: Set<string>,
  position: { x: number; y: number },
  size: BoardSize,
): void {
  markRectOnGrid(occupied, occupantRect(position, size));
}

function buildOccupiedFromPlan(
  occupants: GridOccupantSnapshot[],
  plan: Map<string, { x: number; y: number }>,
  excludeId?: string,
): Set<string> {
  const occupied = new Set<string>();
  for (const occupant of occupants) {
    if (excludeId && occupant.id === excludeId) continue;
    const position = plan.get(occupant.id) ?? occupant.position;
    markRectOnGrid(occupied, occupantRect(position, occupant.size));
  }
  return occupied;
}

function findOverlappingOccupants(
  occupants: GridOccupantSnapshot[],
  position: { x: number; y: number },
  size: BoardSize,
  excludeId: string,
  plan: Map<string, { x: number; y: number }> = new Map(),
): GridOccupantSnapshot[] {
  const targetRect = occupantRect(position, size);
  return occupants.filter((occupant) => {
    if (occupant.id === excludeId) return false;
    const resolved = plan.get(occupant.id) ?? occupant.position;
    return rectsOverlap(targetRect, occupantRect(resolved, occupant.size));
  });
}

export function findNearestOpenSpan({
  span,
  size,
  occupied,
  origin,
  maxSteps = PUSH_SEARCH_STEPS,
}: {
  span?: { cols: number; rows: number };
  size?: BoardSize;
  occupied: Set<string>;
  origin: { x: number; y: number };
  maxSteps?: number;
}): { x: number; y: number } | null {
  const resolvedSize = size ?? {
    width: (span?.cols ?? 1) * GRID_CELL_SIZE,
    height: (span?.rows ?? 1) * GRID_CELL_SIZE,
  };
  const { col: originCol, row: originRow } = worldToCell(origin.x, origin.y);

  for (let radius = 0; radius <= maxSteps; radius += 1) {
    for (let row = originRow - radius; row <= originRow + radius; row += 1) {
      for (let col = originCol - radius; col <= originCol + radius; col += 1) {
        if (col < 0 || row < 0) continue;
        const position = cellToWorld(col, row);
        if (rectIsFree(occupantRect(position, resolvedSize), occupied)) {
          return position;
        }
      }
    }
  }

  return null;
}

export function resolveGridMovePlan(
  occupants: GridOccupantSnapshot[],
  moverId: string,
  landing: { x: number; y: number },
): Map<string, { x: number; y: number }> | null {
  const mover = occupants.find((occupant) => occupant.id === moverId);
  if (!mover) return null;

  const plan = new Map<string, { x: number; y: number }>();
  plan.set(moverId, landing);

  const queue = findOverlappingOccupants(occupants, landing, mover.size, moverId)
    .map((occupant) => occupant.id);
  const queued = new Set<string>(queue);

  while (queue.length > 0) {
    const id = queue.shift();
    if (!id || plan.has(id)) continue;

    const occupant = occupants.find((entry) => entry.id === id);
    if (!occupant) continue;

    const blocked = buildOccupiedFromPlan(occupants, plan, id);
    const nextPosition = findNearestOpenSpan({
      size: occupant.size,
      occupied: blocked,
      origin: occupant.position,
    });
    if (!nextPosition) return null;

    plan.set(id, nextPosition);

    const newlyBlocked = findOverlappingOccupants(
      occupants,
      nextPosition,
      occupant.size,
      id,
      plan,
    );
    for (const blockedOccupant of newlyBlocked) {
      if (blockedOccupant.id === moverId || plan.has(blockedOccupant.id)) continue;
      if (queued.has(blockedOccupant.id)) continue;
      queue.push(blockedOccupant.id);
      queued.add(blockedOccupant.id);
    }
  }

  return plan;
}

export function resolveGridResizePlan(
  occupants: GridOccupantSnapshot[],
  resizerId: string,
  newSize: BoardSize,
): Map<string, { x: number; y: number }> | null {
  const resizer = occupants.find((occupant) => occupant.id === resizerId);
  if (!resizer) return null;

  const resizedOccupants = occupants.map((occupant) =>
    occupant.id === resizerId ? { ...occupant, size: newSize } : occupant,
  );

  return resolveGridMovePlan(resizedOccupants, resizerId, resizer.position);
}

export function previewGridMove({
  occupants,
  moverId,
  size,
  position,
}: {
  occupants: GridOccupantSnapshot[];
  moverId: string;
  size: BoardSize;
  position: { x: number; y: number };
}): GridMovePreview {
  const landing = snapPositionToNearestGrid(position);
  const plan = resolveGridMovePlan(
    occupants.map((occupant) =>
      occupant.id === moverId ? { ...occupant, size } : occupant,
    ),
    moverId,
    landing,
  );

  return {
    landing,
    willPush: plan ? [...plan.keys()].some((id) => id !== moverId) : false,
    canPlace: plan !== null,
  };
}

export function visibleWorldRect(viewport: ViewportLike, boardSize: BoardSize): BoardRect {
  return {
    x: -viewport.pan.x / viewport.zoom,
    y: -viewport.pan.y / viewport.zoom,
    width: boardSize.width / viewport.zoom,
    height: boardSize.height / viewport.zoom,
  };
}

export function visibleCellRange(viewport: ViewportLike, boardSize: BoardSize): {
  colMin: number;
  colMax: number;
  rowMin: number;
  rowMax: number;
} {
  const world = visibleWorldRect(viewport, boardSize);
  return {
    colMin: Math.floor(world.x / GRID_CELL_SIZE),
    colMax: Math.floor((world.x + world.width) / GRID_CELL_SIZE),
    rowMin: Math.floor(world.y / GRID_CELL_SIZE),
    rowMax: Math.floor((world.y + world.height) / GRID_CELL_SIZE),
  };
}

function rectFitsInVisible(rect: BoardRect, visible: BoardRect): boolean {
  return (
    rect.x >= visible.x
    && rect.y >= visible.y
    && rect.x + rect.width <= visible.x + visible.width
    && rect.y + rect.height <= visible.y + visible.height
  );
}

function spiralCellOrigins(
  originCol: number,
  originRow: number,
  maxRadius: number,
): Array<{ col: number; row: number }> {
  const origins: Array<{ col: number; row: number }> = [];
  for (let radius = 0; radius <= maxRadius; radius += 1) {
    for (let row = originRow - radius; row <= originRow + radius; row += 1) {
      for (let col = originCol - radius; col <= originCol + radius; col += 1) {
        if (radius > 0 && Math.abs(col - originCol) !== radius && Math.abs(row - originRow) !== radius) {
          continue;
        }
        origins.push({ col, row });
      }
    }
  }
  return origins;
}

export function findOpenGridCell({
  span,
  size,
  occupied,
  viewport,
  boardSize,
}: {
  span: { cols: number; rows: number };
  size?: BoardSize;
  occupied: Set<string>;
  viewport: ViewportLike;
  boardSize: BoardSize;
}): { x: number; y: number } {
  const resolvedSize = size ?? {
    width: span.cols * GRID_CELL_SIZE,
    height: span.rows * GRID_CELL_SIZE,
  };
  const visible = visibleWorldRect(viewport, boardSize);
  const originCol = Math.round(
    (visible.x + visible.width / 2 - resolvedSize.width / 2) / GRID_CELL_SIZE,
  );
  const originRow = Math.round(
    (visible.y + visible.height / 2 - resolvedSize.height / 2) / GRID_CELL_SIZE,
  );
  const allowNegative = visible.x < 0 || visible.y < 0;
  const maxRadius = FALLBACK_EXPANSION_STEPS + Math.ceil(
    Math.max(visible.width / GRID_CELL_SIZE, visible.height / GRID_CELL_SIZE),
  );

  const tryCell = (col: number, row: number, requireVisible: boolean) => {
    if (!allowNegative && (col < 0 || row < 0)) return null;
    const position = cellToWorld(col, row);
    const rect = occupantRect(position, resolvedSize);
    if (requireVisible && !rectFitsInVisible(rect, visible)) return null;
    return rectIsFree(rect, occupied) ? position : null;
  };

  for (const requireVisible of [true, false]) {
    for (const { col, row } of spiralCellOrigins(originCol, originRow, maxRadius)) {
      const placement = tryCell(col, row, requireVisible);
      if (placement) return placement;
    }
  }

  let maxRow = 0;
  for (const key of occupied) {
    const row = Number(key.split(",")[1]);
    if (Number.isFinite(row) && row + 1 > maxRow) {
      maxRow = row + 1;
    }
  }
  return cellToWorld(Math.max(0, originCol), maxRow);
}

export function deriveTutorBoardTitle(
  item: { kind: VisualKind; id: string; label?: string | null; markdown?: string },
  index: number,
): string {
  if (item.kind === "shape") return `Sketch ${index}`;

  const label = "label" in item ? item.label?.trim() : "";
  if (label) return label;

  if (item.kind === "text" && typeof item.markdown === "string") {
    const line = item.markdown
      .split(/\r?\n/)
      .map((part) => part.trim().replace(/^#{1,6}\s*/, "").trim())
      .find(Boolean);
    if (line) return line;
  }

  return `Tutor Board ${index}`;
}

const TUTOR_HEADER_TITLE_MAX = 52;

/** Shorten long tutor card titles so the header can clip without covering controls. */
export function truncateTutorBoardTitle(title: string, maxLength = TUTOR_HEADER_TITLE_MAX): {
  display: string;
  truncated: boolean;
} {
  const trimmed = title.trim();
  if (trimmed.length <= maxLength) {
    return { display: trimmed, truncated: false };
  }
  return {
    display: `${trimmed.slice(0, maxLength - 1).trimEnd()}…`,
    truncated: true,
  };
}
