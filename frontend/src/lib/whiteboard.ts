/**
 * TS mirror of `backend/app/agent/whiteboard/messages.py`.
 *
 * Pair changes 1:1 with the pydantic file — there is no schema generator.
 */

export const AI_BOARD_TOPIC = "ai_board" as const;
export const USER_BOARD_TOPIC = "user_board" as const;

export interface AiBoardText {
  kind: "text";
  id: string;
  markdown: string;
}

export interface AiBoardPlot {
  kind: "plot";
  id: string;
  expression: string;
  x_min: number;
  x_max: number;
  label?: string | null;
}

export interface AiBoardShape {
  kind: "shape";
  id: string;
  svg: string;
}

export interface AiBoardDiagram {
  kind: "diagram";
  id: string;
  syntax: "mermaid";
  source: string;
  label?: string | null;
}

export type AiBoardItem =
  | AiBoardText
  | AiBoardPlot
  | AiBoardShape
  | AiBoardDiagram;

export interface AiBoardUpdate {
  op: "upsert" | "clear";
  items: AiBoardItem[];
}

export interface UserBoardSnapshot {
  png_b64: string;
  captured_at_ms: number;
  is_empty: boolean;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

export function encodeAiUpdate(update: AiBoardUpdate): Uint8Array {
  return encoder.encode(JSON.stringify(update));
}

export function decodeAiUpdate(payload: Uint8Array): AiBoardUpdate | null {
  try {
    return JSON.parse(decoder.decode(payload)) as AiBoardUpdate;
  } catch {
    return null;
  }
}

export function encodeUserSnapshot(snap: UserBoardSnapshot): Uint8Array {
  return encoder.encode(JSON.stringify(snap));
}

export function decodeUserSnapshot(payload: Uint8Array): UserBoardSnapshot | null {
  try {
    return JSON.parse(decoder.decode(payload)) as UserBoardSnapshot;
  } catch {
    return null;
  }
}
