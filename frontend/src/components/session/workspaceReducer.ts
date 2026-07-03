import type { AiBoardItem } from "../../lib/whiteboard";
import {
  addRectToOccupied,
  clampStickyNoteSize,
  clampStudentCardSize,
  clampToCellSpan,
  COLLAPSED_TUTOR_RIBBON_HEIGHT,
  findOpenGridCell,
  occupiedCells,
  previewGridMove,
  resolveGridMovePlan,
  resolveGridResizePlan,
  snapPositionToNearestGrid,
  spanForSize,
  stickyNoteDefaultSize,
  studentCardDefaultSize,
  tutorCardSizeForKind,
  type GridOccupantSnapshot,
} from "../../lib/boardPlacement";
import type {
  BoardObject,
  HandwritingPanelState,
  InkState,
  Point,
  Size,
  StickyNoteState,
  StudentCardState,
  ViewportState,
  WorkspaceAction,
  WorkspaceState,
} from "./workspaceTypes";

const DEFAULT_HANDWRITING: HandwritingPanelState = {
  position: { x: 0, y: 0 },
  size: studentCardDefaultSize(),
  isCapturing: false,
};

const DEFAULT_VIEWPORT: ViewportState = {
  pan: { x: 0, y: 0 },
  zoom: 1,
};

const DEFAULT_BOARD_SIZE: Size = { width: 900, height: 640 };

const DEFAULT_INK: InkState = {
  tool: "pen",
  color: "#213f35",
  activeTarget: { kind: "private_board" },
};

export const initialWorkspaceState: WorkspaceState = {
  objects: [],
  studentCards: [createStudentCard(1, DEFAULT_HANDWRITING)],
  stickyNotes: [],
  privateBoardStrokes: [],
  ink: DEFAULT_INK,
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
        objects: upsertBoardObjects(state, action.items, action.boardSize),
      };
    case "move_object": {
      return applySmartGridMove(state, action.id, action.position);
    }
    case "resize_object": {
      const existing = state.objects.find((obj) => obj.id === action.id);
      if (!existing) return state;

      const previousSize = existing.size ?? tutorCardSizeForKind(existing.kind);
      const size = clampToCellSpan(action.size);
      if (sizesEqual(previousSize, size)) return state;

      return applySmartGridResize(state, action.id, size);
    }
    case "activate_object":
      return {
        ...state,
        objects: state.objects.map((obj) =>
          obj.id === action.id ? { ...obj, collapsed: false } : obj,
        ),
      };
    case "collapse_object":
      return {
        ...state,
        objects: state.objects.map((obj) =>
          obj.id === action.id ? { ...obj, collapsed: true } : obj,
        ),
      };
    case "add_student_card": {
      const nextNumber = nextStudentCardNumber(state.studentCards);
      const size = studentCardDefaultSize();
      const resolvedBoardSize = action.boardSize ?? DEFAULT_BOARD_SIZE;
      const occupied = occupiedCells(state.objects, state.studentCards, state.stickyNotes);
      const position = findOpenGridCell({
        span: spanForSize(size),
        size,
        occupied,
        viewport: state.viewport,
        boardSize: resolvedBoardSize,
      });
      addRectToOccupied(occupied, position, size);
      return {
        ...state,
        studentCards: [
          ...state.studentCards,
          createStudentCard(nextNumber, { position, size, isCapturing: false }),
        ],
      };
    }
    case "add_sticky_note": {
      const nextNumber = nextStickyNoteNumber(state.stickyNotes);
      const size = stickyNoteDefaultSize();
      const resolvedBoardSize = action.boardSize ?? DEFAULT_BOARD_SIZE;
      const occupied = occupiedCells(state.objects, state.studentCards, state.stickyNotes);
      const position = findOpenGridCell({
        span: spanForSize(size),
        size,
        occupied,
        viewport: state.viewport,
        boardSize: resolvedBoardSize,
      });
      return {
        ...state,
        stickyNotes: [
          ...state.stickyNotes,
          createStickyNote(nextNumber, position, size),
        ],
      };
    }
    case "move_sticky_note": {
      return applySmartGridMove(state, action.id, action.position);
    }
    case "resize_sticky_note": {
      const size = clampStickyNoteSize(action.size);
      const existing = state.stickyNotes.find((note) => note.id === action.id);
      if (!existing || sizesEqual(existing.size, size)) return state;

      return applySmartGridResize(state, action.id, size);
    }
    case "update_sticky_note_text": {
      const existing = state.stickyNotes.find((note) => note.id === action.id);
      if (!existing || existing.text === action.text) return state;
      return {
        ...state,
        stickyNotes: state.stickyNotes.map((note) =>
          note.id === action.id ? { ...note, text: action.text } : note,
        ),
      };
    }
    case "delete_student_card": {
      const existing = state.studentCards.find((card) => card.id === action.id);
      if (!existing) return state;
      const ink =
        state.ink.activeTarget.kind === "student_card"
        && state.ink.activeTarget.cardId === action.id
          ? { ...state.ink, activeTarget: { kind: "private_board" as const } }
          : state.ink;
      return {
        ...state,
        studentCards: state.studentCards.filter((card) => card.id !== action.id),
        ink,
      };
    }
    case "delete_sticky_note": {
      if (!state.stickyNotes.some((note) => note.id === action.id)) return state;
      return {
        ...state,
        stickyNotes: state.stickyNotes.filter((note) => note.id !== action.id),
      };
    }
    case "set_ink_tool":
      return {
        ...state,
        ink: { ...state.ink, tool: action.tool },
      };
    case "set_ink_color":
      return {
        ...state,
        ink: { ...state.ink, color: action.color },
      };
    case "set_active_ink_target":
      return {
        ...state,
        ink: { ...state.ink, activeTarget: action.target },
      };
    case "commit_private_board_stroke":
      return {
        ...state,
        privateBoardStrokes: [...state.privateBoardStrokes, action.stroke],
        ink: { ...state.ink, activeTarget: { kind: "private_board" } },
      };
    case "undo_active_ink":
      if (state.ink.activeTarget.kind !== "private_board" || state.privateBoardStrokes.length === 0) {
        return state;
      }
      return {
        ...state,
        privateBoardStrokes: state.privateBoardStrokes.slice(0, -1),
      };
    case "clear_active_ink":
      if (state.ink.activeTarget.kind !== "private_board" || state.privateBoardStrokes.length === 0) {
        return state;
      }
      return {
        ...state,
        privateBoardStrokes: [],
      };
    case "move_student_card": {
      return applySmartGridMove(state, action.id, action.position);
    }
    case "resize_student_card": {
      const size = clampStudentCardSize(action.size);
      const existing = state.studentCards.find((card) => card.id === action.id);
      if (!existing || sizesEqual(existing.size, size)) {
        return state;
      }

      return applySmartGridResize(state, action.id, size);
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

function upsertBoardObjects(
  state: WorkspaceState,
  items: AiBoardItem[],
  boardSize?: Size,
): BoardObject[] {
  if (items.length === 0) return state.objects;

  const incomingIds = new Set(items.map((item) => item.id));
  const existingById = new Map(state.objects.map((obj) => [obj.id, obj]));
  const retained = state.objects.filter((obj) => !incomingIds.has(obj.id));
  const occupied = occupiedCells(state.objects, state.studentCards, state.stickyNotes);
  const resolvedBoardSize = boardSize ?? DEFAULT_BOARD_SIZE;

  const incoming = items.map((item) => {
    const existing = existingById.get(item.id);
    if (existing) {
      return updateBoardObject(existing, item);
    }

    const size = tutorCardSizeForKind(item.kind);
    const position = findOpenGridCell({
      span: spanForSize(size),
      size,
      occupied,
      viewport: state.viewport,
      boardSize: resolvedBoardSize,
    });
    const created = createBoardObject(item, position, size, false);
    addRectToOccupied(occupied, position, created.size ?? size);
    return created;
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

function createStickyNote(number: number, position: Point, size: Size): StickyNoteState {
  return {
    id: `sticky-note-${number}`,
    position,
    size,
    text: "",
  };
}

function nextStickyNoteNumber(notes: StickyNoteState[]): number {
  const numbers = notes.map((note) => {
    const match = /^sticky-note-(\d+)$/.exec(note.id);
    return match ? Number(match[1]) : 0;
  });
  return Math.max(0, ...numbers) + 1;
}

function tutorOccupantSize(object: BoardObject): Size {
  const size = object.size ?? tutorCardSizeForKind(object.kind);
  if (object.collapsed) {
    return { width: size.width, height: COLLAPSED_TUTOR_RIBBON_HEIGHT };
  }
  return size;
}

function collectGridOccupants(state: WorkspaceState): GridOccupantSnapshot[] {
  const tutors = state.objects.map((object) => ({
    id: object.id,
    position: object.position,
    size: tutorOccupantSize(object),
  }));
  const students = state.studentCards.map((card) => ({
    id: card.id,
    position: card.position,
    size: card.size,
  }));
  const notes = state.stickyNotes.map((note) => ({
    id: note.id,
    position: note.position,
    size: note.size,
  }));
  return [...tutors, ...students, ...notes];
}

export function buildGridMovePreview(
  state: WorkspaceState,
  moverId: string,
  size: Size,
  livePosition: Point,
) {
  return previewGridMove({
    occupants: collectGridOccupants(state),
    moverId,
    size,
    position: livePosition,
  });
}

function applySmartGridMove(
  state: WorkspaceState,
  moverId: string,
  livePosition: Point,
): WorkspaceState {
  const occupants = collectGridOccupants(state);
  const mover = occupants.find((occupant) => occupant.id === moverId);
  if (!mover) return state;

  const landing = snapPositionToNearestGrid(livePosition);
  if (pointsEqual(mover.position, landing)) return state;

  const plan = resolveGridMovePlan(occupants, moverId, landing);
  if (!plan) return state;

  return {
    ...state,
    objects: state.objects.map((object) => {
      const next = plan.get(object.id);
      return next ? { ...object, position: next } : object;
    }),
    studentCards: state.studentCards.map((card) => {
      const next = plan.get(card.id);
      return next ? { ...card, position: next } : card;
    }),
    stickyNotes: state.stickyNotes.map((note) => {
      const next = plan.get(note.id);
      return next ? { ...note, position: next } : note;
    }),
  };
}

function applySmartGridResize(
  state: WorkspaceState,
  resizerId: string,
  size: Size,
): WorkspaceState {
  const occupants = collectGridOccupants(state);
  const resizer = occupants.find((occupant) => occupant.id === resizerId);
  if (!resizer) return state;

  const plan = resolveGridResizePlan(occupants, resizerId, size);
  if (!plan) return state;

  return {
    ...state,
    objects: state.objects.map((object) => {
      if (object.id === resizerId) return { ...object, size };
      const next = plan.get(object.id);
      return next ? { ...object, position: next } : object;
    }),
    studentCards: state.studentCards.map((card) => {
      if (card.id === resizerId) return { ...card, size };
      const next = plan.get(card.id);
      return next ? { ...card, position: next } : card;
    }),
    stickyNotes: state.stickyNotes.map((note) => {
      if (note.id === resizerId) return { ...note, size };
      const next = plan.get(note.id);
      return next ? { ...note, position: next } : note;
    }),
  };
}

function updateBoardObject(existing: BoardObject, item: AiBoardItem): BoardObject {
  switch (item.kind) {
    case "text":
      return { ...existing, kind: item.kind, item };
    case "plot":
      return { ...existing, kind: item.kind, item };
    case "shape":
      return { ...existing, kind: item.kind, item };
    case "diagram":
      return { ...existing, kind: item.kind, item };
  }
}

function createBoardObject(
  item: AiBoardItem,
  position: Point,
  size: Size,
  collapsed = false,
): BoardObject {
  const clampedSize = clampToCellSpan(size);
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

function normalizeStudentCardLabel(label: string, cardId: string): string {
  const trimmed = label.trim();
  if (trimmed) return trimmed.slice(0, 64);
  const match = /^student-card-(\d+)$/.exec(cardId);
  return match ? `Student Card ${match[1]}` : "Student Card";
}

function pointsEqual(a: Point, b: Point): boolean {
  return Math.round(a.x) === Math.round(b.x) && Math.round(a.y) === Math.round(b.y);
}

function sizesEqual(a: Size, b: Size): boolean {
  return Math.round(a.width) === Math.round(b.width)
    && Math.round(a.height) === Math.round(b.height);
}
