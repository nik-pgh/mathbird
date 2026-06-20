/** Wire format for the ``session_progress`` LiveKit data channel. */

export const SESSION_PROGRESS_TOPIC = "session_progress";

export interface FocusPointer {
  chapter_id: string;
  concept_id: string;
  problem_id: string;
}

export interface ProgressSummary {
  mastered: number;
  in_progress: number;
  total: number;
}

export interface ProblemProgressSnapshot {
  problem_id: string;
  chapter_id: string;
  concept_id: string;
  label: string;
  status: "not_started" | "in_progress" | "mastered";
  attempts: number;
}

export interface SessionProgressUpdate {
  op: "snapshot" | "patch";
  focus: FocusPointer | null;
  next_suggestion: FocusPointer | null;
  summary: ProgressSummary;
  nodes: ProblemProgressSnapshot[];
}

export function decodeSessionProgressUpdate(
  payload: Uint8Array,
): SessionProgressUpdate | null {
  try {
    const text = new TextDecoder().decode(payload);
    return JSON.parse(text) as SessionProgressUpdate;
  } catch {
    return null;
  }
}
