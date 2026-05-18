import { useCallback } from "react";
import { useDataChannel } from "@livekit/components-react";

/**
 * Thin wrapper around `useDataChannel` typed for a single board topic.
 *
 * - `onMessage`: called with the decoded payload (or `null` if decoding failed)
 *   for every packet on this topic.
 * - returns a `send` callback that publishes the encoded payload reliably.
 */
export function useBoardChannel<T extends string, M>(opts: {
  topic: T;
  decode: (payload: Uint8Array) => M | null;
  encode: (msg: M) => Uint8Array;
  onMessage?: (msg: M) => void;
}) {
  const { topic, decode, encode, onMessage } = opts;

  const { send } = useDataChannel(topic, (raw) => {
    if (!onMessage) return;
    const decoded = decode(raw.payload);
    if (decoded !== null) onMessage(decoded);
  });

  const sendMessage = useCallback(
    async (msg: M) => {
      await send(encode(msg), { reliable: true, topic });
    },
    [send, encode, topic]
  );

  return { send: sendMessage };
}
