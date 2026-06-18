import type { AiBoardItem } from "../../lib/whiteboard";
import type {
  BoardObject,
  HandwritingPanelState,
  Point,
  Size,
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
  handwriting: DEFAULT_HANDWRITING,
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
    case "move_handwriting":
      if (pointsEqual(state.handwriting.position, action.position)) return state;
      return {
        ...state,
        handwriting: { ...state.handwriting, position: action.position },
      };
    case "resize_handwriting":
      if (sizesEqual(state.handwriting.size, clampPanelSize(action.size))) {
        return state;
      }
      return {
        ...state,
        handwriting: {
          ...state.handwriting,
          size: clampPanelSize(action.size),
        },
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
    case "set_capturing":
      if (state.handwriting.isCapturing === action.value) return state;
      return {
        ...state,
        handwriting: { ...state.handwriting, isCapturing: action.value },
      };
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
