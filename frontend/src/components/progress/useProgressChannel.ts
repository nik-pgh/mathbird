import { useDataChannel } from "@livekit/components-react";
import { useState } from "react";
import {
  SESSION_PROGRESS_TOPIC,
  decodeSessionProgressUpdate,
  type SessionProgressUpdate,
} from "../../lib/progress";

function snapshotsEqual(
  left: SessionProgressUpdate | null,
  right: SessionProgressUpdate,
): boolean {
  if (left === null) {
    return false;
  }
  return JSON.stringify(left) === JSON.stringify(right);
}

function mergeProgressUpdate(
  current: SessionProgressUpdate | null,
  incoming: SessionProgressUpdate,
): SessionProgressUpdate {
  if (incoming.op === "snapshot" || current === null) {
    return incoming;
  }

  const nodesById = new Map(current.nodes.map((node) => [node.problem_id, node]));
  for (const node of incoming.nodes) {
    nodesById.set(node.problem_id, node);
  }

  const conceptsById = new Map(
    (current.concepts ?? []).map((concept) => [concept.concept_id, concept]),
  );
  for (const concept of incoming.concepts ?? []) {
    conceptsById.set(concept.concept_id, concept);
  }

  return {
    op: "snapshot",
    focus: incoming.focus,
    next_suggestion: incoming.next_suggestion,
    summary: incoming.summary,
    nodes: [...nodesById.values()],
    concepts: [...conceptsById.values()],
  };
}

export function useProgressChannel() {
  const [snapshot, setSnapshot] = useState<SessionProgressUpdate | null>(null);

  useDataChannel(SESSION_PROGRESS_TOPIC, (raw) => {
    const decoded = decodeSessionProgressUpdate(raw.payload);
    if (decoded !== null) {
      setSnapshot((current) => {
        const merged = mergeProgressUpdate(current, decoded);
        return snapshotsEqual(current, merged) ? current : merged;
      });
    }
  });

  return snapshot;
}
