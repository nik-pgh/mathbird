import { useDataChannel } from "@livekit/components-react";
import { useState } from "react";
import {
  SESSION_PROGRESS_TOPIC,
  decodeSessionProgressUpdate,
  type SessionProgressUpdate,
} from "../../lib/progress";

export function useProgressChannel() {
  const [snapshot, setSnapshot] = useState<SessionProgressUpdate | null>(null);

  useDataChannel(SESSION_PROGRESS_TOPIC, (raw) => {
    const decoded = decodeSessionProgressUpdate(raw.payload);
    if (decoded !== null) {
      setSnapshot(decoded);
    }
  });

  return snapshot;
}
