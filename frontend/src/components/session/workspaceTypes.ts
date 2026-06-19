import type { AiBoardItem } from "../../lib/whiteboard";

export interface Point {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

type BoardObjectByKind = {
  [Item in AiBoardItem as Item["kind"]]: {
    id: string;
    kind: Item["kind"];
    item: Item;
    position: Point;
    size?: Size;
    collapsed?: boolean;
  };
};

export type BoardObject = BoardObjectByKind[keyof BoardObjectByKind];

export interface HandwritingPanelState {
  position: Point;
  size: Size;
  isCapturing: boolean;
}

export interface StudentCardState {
  id: string;
  label: string;
  position: Point;
  size: Size;
  isCapturing: boolean;
}

export interface ViewportState {
  pan: Point;
  zoom: number;
}

export interface WorkspaceOverlayState {
  textbook: "large" | "small";
  transcriptOpen: boolean;
}

export interface WorkspaceState {
  objects: BoardObject[];
  studentCards: StudentCardState[];
  viewport: ViewportState;
  overlays: WorkspaceOverlayState;
}

export type WorkspaceAction =
  | { type: "ai_clear" }
  | { type: "ai_upsert"; items: AiBoardItem[]; boardSize?: Size }
  | { type: "move_object"; id: string; position: Point }
  | { type: "resize_object"; id: string; size: Size; boardSize?: Size }
  | { type: "activate_object"; id: string; boardSize?: Size }
  | { type: "collapse_object"; id: string; boardSize?: Size }
  | { type: "add_student_card"; boardSize: Size }
  | { type: "move_student_card"; id: string; position: Point }
  | { type: "resize_student_card"; id: string; size: Size }
  | { type: "rename_student_card"; id: string; label: string }
  | { type: "set_student_card_capturing"; id: string; value: boolean }
  | { type: "set_viewport"; viewport: ViewportState }
  | { type: "reset_viewport" }
  | { type: "set_textbook"; value: "large" | "small" }
  | { type: "toggle_transcript" };
