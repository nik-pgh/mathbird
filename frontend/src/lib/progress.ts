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
  // Full ordinal mastery level (5 values). introduced/practicing/proficient
  // are the partial-progress states between not_started and mastered.
  status:
    | "not_started"
    | "introduced"
    | "practicing"
    | "proficient"
    | "mastered";
  attempts: number;
}

export interface ConceptProgressSnapshot {
  // Concept-level progress row (additive; older clients can ignore it).
  concept_id: string;
  chapter_id: string;
  label: string;
  level:
    | "not_started"
    | "introduced"
    | "practicing"
    | "proficient"
    | "mastered";
  has_open_misconceptions: boolean;
}

export interface SessionProgressUpdate {
  op: "snapshot" | "patch";
  focus: FocusPointer | null;
  next_suggestion: FocusPointer | null;
  summary: ProgressSummary;
  nodes: ProblemProgressSnapshot[];
  // Additive: pre-Phase-D payloads omit it; defaults to empty.
  concepts?: ConceptProgressSnapshot[];
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
