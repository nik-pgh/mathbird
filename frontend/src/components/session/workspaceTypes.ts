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
  };
};

export type BoardObject = BoardObjectByKind[keyof BoardObjectByKind];

export interface HandwritingPanelState {
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
  handwriting: HandwritingPanelState;
  viewport: ViewportState;
  overlays: WorkspaceOverlayState;
}

export type WorkspaceAction =
  | { type: "ai_clear" }
  | { type: "ai_upsert"; items: AiBoardItem[] }
  | { type: "move_object"; id: string; position: Point }
  | { type: "move_handwriting"; position: Point }
  | { type: "resize_handwriting"; size: Size }
  | { type: "set_viewport"; viewport: ViewportState }
  | { type: "reset_viewport" }
  | { type: "set_textbook"; value: "large" | "small" }
  | { type: "toggle_transcript" }
  | { type: "set_capturing"; value: boolean };
