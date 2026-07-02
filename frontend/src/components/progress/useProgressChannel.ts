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

export function useProgressChannel() {
  const [snapshot, setSnapshot] = useState<SessionProgressUpdate | null>(null);

  useDataChannel(SESSION_PROGRESS_TOPIC, (raw) => {
    const decoded = decodeSessionProgressUpdate(raw.payload);
    if (decoded !== null) {
      setSnapshot((current) =>
        snapshotsEqual(current, decoded) ? current : decoded,
      );
    }
  });

  return snapshot;
}
