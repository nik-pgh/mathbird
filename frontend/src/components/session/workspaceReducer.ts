import type { AiBoardItem } from "../../lib/whiteboard";
import {
  clampTutorCardSize,
  findOpenBoardPosition,
  layoutTutorFlow,
  tutorCardSizeForKind,
  tutorFlowMaxColumnHeight,
  type BoardRect,
} from "../../lib/boardPlacement";
import type {
  BoardObject,
  HandwritingPanelState,
  Point,
  Size,
  StudentCardState,
  ViewportState,
  WorkspaceAction,
  WorkspaceState,
} from "./workspaceTypes";

const DEFAULT_HANDWRITING: HandwritingPanelState = {
  position: { x: 56, y: 76 },
  size: { width: 520, height: 390 },
  isCapturing: false,
};

const DEFAULT_VIEWPORT: ViewportState = {
  pan: { x: 0, y: 0 },
  zoom: 1,
};

const DEFAULT_TUTOR_POSITION: Point = { x: 36, y: 36 };

export const initialWorkspaceState: WorkspaceState = {
  objects: [],
  studentCards: [createStudentCard(1, DEFAULT_HANDWRITING)],
  viewport: DEFAULT_VIEWPORT,
  overlays: {
    textbook: "small",
    transcriptOpen: false,
  },
};

export function workspaceReducer(
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState {
  switch (action.type) {
    case "ai_clear":
      return { ...state, objects: [] };
    case "ai_upsert":
      return {
        ...state,
        objects: reflowTutorObjects(
          upsertBoardObjects(state, action.items),
          action.boardSize,
        ),
      };
    case "move_object": {
      const origin = flowOriginFromMovedObject(state.objects, action.id, action.position);
      return {
        ...state,
        objects: reflowTutorObjects(
          state.objects.map((obj, index) => (
            index === 0 ? { ...obj, position: origin } : obj
          )),
        ),
      };
    }
    case "resize_object":
      return {
        ...state,
        objects: reflowTutorObjects(
          state.objects.map((obj) =>
            obj.id === action.id ? { ...obj, size: clampTutorCardSize(action.size) } : obj,
          ),
          action.boardSize,
        ),
      };
    case "activate_object":
      return {
        ...state,
        objects: reflowTutorObjects(
          state.objects.map((obj) => ({
            ...obj,
            collapsed: obj.id !== action.id,
          })),
          action.boardSize,
        ),
      };
    case "add_student_card": {
      const nextNumber = nextStudentCardNumber(state.studentCards);
      const size = DEFAULT_HANDWRITING.size;
      const position = findOpenBoardPosition({
        size,
        occupied: occupiedRects(state),
        viewport: {
          x: 0,
          y: 0,
          width: action.boardSize.width,
          height: action.boardSize.height,
        },
      });
      return {
        ...state,
        studentCards: [
          ...state.studentCards,
          createStudentCard(nextNumber, { position, size, isCapturing: false }),
        ],
      };
    }
    case "move_student_card": {
      const existing = state.studentCards.find((card) => card.id === action.id);
      if (!existing || pointsEqual(existing.position, action.position)) return state;
      return {
        ...state,
        studentCards: state.studentCards.map((card) =>
          card.id === action.id ? { ...card, position: action.position } : card,
        ),
      };
    }
    case "resize_student_card": {
      const size = clampPanelSize(action.size);
      const existing = state.studentCards.find((card) => card.id === action.id);
      if (!existing || sizesEqual(existing.size, size)) {
        return state;
      }
      return {
        ...state,
        studentCards: state.studentCards.map((card) =>
          card.id === action.id ? { ...card, size } : card,
        ),
      };
    }
    case "rename_student_card":
      return {
        ...state,
        studentCards: state.studentCards.map((card) =>
          card.id === action.id
            ? { ...card, label: normalizeStudentCardLabel(action.label, card.id) }
            : card,
        ),
      };
    case "set_textbook":
      return {
        ...state,
        overlays: { ...state.overlays, textbook: action.value },
      };
    case "toggle_transcript":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          transcriptOpen: !state.overlays.transcriptOpen,
        },
      };
    case "set_student_card_capturing": {
      const existing = state.studentCards.find((card) => card.id === action.id);
      if (!existing || existing.isCapturing === action.value) return state;
      return {
        ...state,
        studentCards: state.studentCards.map((card) =>
          card.id === action.id ? { ...card, isCapturing: action.value } : card,
        ),
      };
    }
    case "set_viewport":
      return { ...state, viewport: action.viewport };
    case "reset_viewport":
      return { ...state, viewport: DEFAULT_VIEWPORT };
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}

function upsertBoardObjects(state: WorkspaceState, items: AiBoardItem[]): BoardObject[] {
  if (items.length === 0) return state.objects;

  const incomingIds = new Set(items.map((item) => item.id));
  const activeId = items[items.length - 1]?.id;
  const existingById = new Map(state.objects.map((obj) => [obj.id, obj]));
  const activePosition = currentTutorFocusPosition(state.objects);
  const retained = state.objects
    .filter((obj) => !incomingIds.has(obj.id))
    .map((obj) => ({ ...obj, collapsed: true }));

  const incoming = items.map((item) => {
    const existing = existingById.get(item.id);
    const size = existing?.size ?? tutorCardSizeForKind(item.kind);
    const position = existing?.position ?? activePosition;
    return createBoardObject(item, position, size, item.id !== activeId);
  });

  return [...retained, ...incoming];
}

function createStudentCard(
  number: number,
  state: HandwritingPanelState,
): StudentCardState {
  return {
    id: `student-card-${number}`,
    label: `Student Card ${number}`,
    position: state.position,
    size: state.size,
    isCapturing: state.isCapturing,
  };
}

function nextStudentCardNumber(cards: StudentCardState[]): number {
  const numbers = cards.map((card) => {
    const match = /^student-card-(\d+)$/.exec(card.id);
    return match ? Number(match[1]) : 0;
  });
  return Math.max(1, ...numbers) + 1;
}

function occupiedRects(state: WorkspaceState): BoardRect[] {
  const studentRects = state.studentCards.map((card) => ({
    x: card.position.x,
    y: card.position.y,
    width: card.size.width,
    height: card.size.height,
  }));
  const objectRects = state.objects.map((object) => {
    const size = object.size ?? tutorCardSizeForKind(object.kind);
    return {
      x: object.position.x,
      y: object.position.y,
      width: size.width,
      height: size.height,
    };
  });
  return [...studentRects, ...objectRects];
}

function createBoardObject(
  item: AiBoardItem,
  position: Point,
  size: Size,
  collapsed = false,
): BoardObject {
  const clampedSize = clampTutorCardSize(size);
  switch (item.kind) {
    case "text":
      return { id: item.id, kind: item.kind, item, position, size: clampedSize, collapsed };
    case "plot":
      return { id: item.id, kind: item.kind, item, position, size: clampedSize, collapsed };
    case "shape":
      return { id: item.id, kind: item.kind, item, position, size: clampedSize, collapsed };
    case "diagram":
      return { id: item.id, kind: item.kind, item, position, size: clampedSize, collapsed };
  }
}

function currentTutorFocusPosition(objects: BoardObject[]): Point {
  const active = objects.find((obj) => !obj.collapsed);
  return active?.position ?? objects.at(-1)?.position ?? DEFAULT_TUTOR_POSITION;
}

function reflowTutorObjects(objects: BoardObject[], boardSize?: Size): BoardObject[] {
  if (objects.length === 0) return objects;
  const origin = objects[0].position;
  const layout = layoutTutorFlow({
    origin,
    items: objects.map((object) => ({
      id: object.id,
      collapsed: object.collapsed,
      size: object.size ?? tutorCardSizeForKind(object.kind),
    })),
    maxColumnHeight: tutorFlowMaxColumnHeight(boardSize?.height ?? 640),
  });

  return objects.map((object) => ({
    ...object,
    position: layout.positions[object.id] ?? object.position,
  }));
}

function flowOriginFromMovedObject(
  objects: BoardObject[],
  id: string,
  nextPosition: Point,
): Point {
  const moved = objects.find((object) => object.id === id);
  const first = objects[0];
  if (!moved || !first) return nextPosition;
  return {
    x: first.position.x + (nextPosition.x - moved.position.x),
    y: first.position.y + (nextPosition.y - moved.position.y),
  };
}

function normalizeStudentCardLabel(label: string, cardId: string): string {
  const trimmed = label.trim();
  if (trimmed) return trimmed.slice(0, 64);
  const match = /^student-card-(\d+)$/.exec(cardId);
  return match ? `Student Card ${match[1]}` : "Student Card";
}

function clampPanelSize(size: Size): Size {
  const aspectWidth = Math.max(size.width, size.height / 0.75);
  const width = Math.max(280, Math.min(860, aspectWidth));
  return {
    width,
    height: width * 0.75,
  };
}

function pointsEqual(a: Point, b: Point): boolean {
  return Math.round(a.x) === Math.round(b.x) && Math.round(a.y) === Math.round(b.y);
}

function sizesEqual(a: Size, b: Size): boolean {
  return Math.round(a.width) === Math.round(b.width)
    && Math.round(a.height) === Math.round(b.height);
}
