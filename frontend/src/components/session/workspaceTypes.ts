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

export type InkTool = "pen" | "eraser";

export type InkColor = "#213f35" | "#ff775f" | "#2f6fed" | "#7c4dff";

export type InkPoint = [number, number, number];

export type InkTarget =
  | { kind: "private_board" }
  | { kind: "student_card"; cardId: string };

export interface InkStroke {
  id: string;
  target: InkTarget;
  tool: InkTool;
  color: InkColor;
  points: InkPoint[];
}

export interface PrivateBoardInkStroke extends Omit<InkStroke, "target"> {
  target: { kind: "private_board" };
}

export interface InkState {
  tool: InkTool;
  color: InkColor;
  activeTarget: InkTarget;
}

export interface StickyNoteState {
  id: string;
  position: Point;
  size: Size;
  text: string;
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
  stickyNotes: StickyNoteState[];
  privateBoardStrokes: PrivateBoardInkStroke[];
  ink: InkState;
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
  | { type: "add_sticky_note"; boardSize: Size }
  | { type: "move_sticky_note"; id: string; position: Point }
  | { type: "resize_sticky_note"; id: string; size: Size }
  | { type: "update_sticky_note_text"; id: string; text: string }
  | { type: "delete_student_card"; id: string }
  | { type: "delete_sticky_note"; id: string }
  | { type: "set_ink_tool"; tool: InkTool }
  | { type: "set_ink_color"; color: InkColor }
  | { type: "set_active_ink_target"; target: InkTarget }
  | { type: "commit_private_board_stroke"; stroke: PrivateBoardInkStroke }
  | { type: "undo_active_ink" }
  | { type: "clear_active_ink" }
  | { type: "set_viewport"; viewport: ViewportState }
  | { type: "reset_viewport" }
  | { type: "set_textbook"; value: "large" | "small" }
  | { type: "toggle_transcript" };
