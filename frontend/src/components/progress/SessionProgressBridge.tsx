import { useProgressChannel } from "./useProgressChannel";

/** Subscribes to session_progress inside LiveKitRoom; UI deferred to P4. */
export default function SessionProgressBridge() {
  useProgressChannel();
  return null;
}
