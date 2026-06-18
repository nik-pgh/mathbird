import type { AiBoardItem } from "../../lib/whiteboard";
import {
  findOpenBoardPosition,
  tutorCardSizeForKind,
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
      return { ...state, objects: upsertBoardObjects(state.objects, action.items) };
    case "move_object":
      return {
        ...state,
        objects: state.objects.map((obj) =>
          obj.id === action.id ? { ...obj, position: action.position } : obj,
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

function upsertBoardObjects(
  current: BoardObject[],
  items: AiBoardItem[],
): BoardObject[] {
  const next = new Map(current.map((obj) => [obj.id, obj]));
  for (const item of items) {
    const existing = next.get(item.id);
    next.set(item.id, createBoardObject(item, existing, next.size));
  }
  return Array.from(next.values());
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
  existing: BoardObject | undefined,
  index: number,
): BoardObject {
  const position = existing?.position ?? defaultObjectPosition(index);
  const size = existing?.size;

  switch (item.kind) {
    case "text":
      return { id: item.id, kind: item.kind, item, position, size };
    case "plot":
      return { id: item.id, kind: item.kind, item, position, size };
    case "shape":
      return { id: item.id, kind: item.kind, item, position, size };
    case "diagram":
      return { id: item.id, kind: item.kind, item, position, size };
  }
}

function defaultObjectPosition(index: number): Point {
  const column = index % 2;
  const row = Math.floor(index / 2);
  return {
    x: 36 + column * 356,
    y: 36 + row * 160,
  };
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
