import { useCallback, useState } from "react";
import {
  useLocalParticipant,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";

interface Props {
  /** Session-level status from the parent (LiveKit may not yet be attached). */
  status: "connecting" | "connected" | "disconnected";
  /** Called when the user taps the end (●) button. */
  onEnd: () => void;
}

export default function VoiceComposer({ status, onEnd }: Props) {
  return status === "connected" ? (
    <ConnectedComposer onEnd={onEnd} />
  ) : (
    <PlaceholderComposer status={status} onEnd={onEnd} />
  );
}

function ConnectedComposer({ onEnd }: { onEnd: () => void }) {
  const { state } = useVoiceAssistant();
  const { localParticipant } = useLocalParticipant();
  const micEnabled =
    localParticipant.getTrackPublication(Track.Source.Microphone)?.isMuted ===
    false;
  const [, force] = useState(0);

  const toggleMute = useCallback(async () => {
    await localParticipant.setMicrophoneEnabled(!micEnabled);
    force((n) => n + 1); // mic publication state is imperative; nudge a re-render
  }, [localParticipant, micEnabled]);

  const label =
    state === "speaking"
      ? "Tutor is speaking…"
      : state === "thinking"
      ? "Thinking…"
      : state === "listening"
      ? "Listening…"
      : "Connecting…";

  return (
    <div className={`voice-composer ${micEnabled ? "" : "muted"}`}>
      <div className="wrap">
        <div className="state">
          <Bars />
          {label}
        </div>
        <button
          className="icon-btn"
          onClick={toggleMute}
          title={micEnabled ? "Mute" : "Unmute"}
          aria-label={micEnabled ? "Mute microphone" : "Unmute microphone"}
        >
          {micEnabled ? "⏸" : "▶"}
        </button>
        <button
          className="icon-btn primary"
          onClick={onEnd}
          title="End session"
          aria-label="End session"
        >
          ●
        </button>
      </div>
    </div>
  );
}

function PlaceholderComposer({
  status,
  onEnd,
}: {
  status: "connecting" | "disconnected";
  onEnd: () => void;
}) {
  return (
    <div className={`voice-composer ${status}`}>
      <div className="wrap">
        <div className="state">
          <Bars />
          {status === "connecting" ? "Connecting…" : "Disconnected"}
        </div>
        <button
          className="icon-btn"
          disabled
          aria-label="Mute (unavailable while disconnected)"
        >
          ⏸
        </button>
        <button
          className="icon-btn primary"
          onClick={onEnd}
          aria-label="End session"
        >
          ●
        </button>
      </div>
    </div>
  );
}

function Bars() {
  return (
    <div className="bars" aria-hidden>
      <span />
      <span />
      <span />
      <span />
      <span />
    </div>
  );
}
