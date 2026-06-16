import {
  useTrackToggle,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import type { ReactNode } from "react";
import CanvasControls from "./CanvasControls";
import type { ViewportState } from "./workspaceTypes";

interface Props {
  /** Session-level status from the parent (LiveKit may not yet be attached). */
  status: "connecting" | "connected" | "disconnected";
  /** Whether the transcript overlay is open on the shared board. */
  transcriptOpen: boolean;
  /** Toggles the transcript overlay from the footer controls. */
  onTranscriptToggle: () => void;
  /** Called when the user taps the end (●) button. */
  onEnd: () => void;
  viewport: ViewportState;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetViewport: () => void;
}

export default function VoiceComposer({
  status,
  transcriptOpen,
  onTranscriptToggle,
  onEnd,
  viewport,
  onZoomIn,
  onZoomOut,
  onResetViewport,
}: Props) {
  return status === "connected" ? (
    <ConnectedComposer
      transcriptOpen={transcriptOpen}
      onTranscriptToggle={onTranscriptToggle}
      onEnd={onEnd}
      viewport={viewport}
      onZoomIn={onZoomIn}
      onZoomOut={onZoomOut}
      onResetViewport={onResetViewport}
    />
  ) : (
    <PlaceholderComposer
      status={status}
      transcriptOpen={transcriptOpen}
      onTranscriptToggle={onTranscriptToggle}
      onEnd={onEnd}
      viewport={viewport}
      onZoomIn={onZoomIn}
      onZoomOut={onZoomOut}
      onResetViewport={onResetViewport}
    />
  );
}

function VoiceFooter({
  className,
  viewport,
  onZoomIn,
  onZoomOut,
  onResetViewport,
  children,
}: {
  className?: string;
  viewport: ViewportState;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetViewport: () => void;
  children: ReactNode;
}) {
  return (
    <div className={`voice-composer ${className ?? ""}`.trim()}>
      <div className="voice-composer-main">{children}</div>
      <CanvasControls
        viewport={viewport}
        onZoomIn={onZoomIn}
        onZoomOut={onZoomOut}
        onReset={onResetViewport}
      />
    </div>
  );
}

function ConnectedComposer({
  transcriptOpen,
  onTranscriptToggle,
  onEnd,
  viewport,
  onZoomIn,
  onZoomOut,
  onResetViewport,
}: {
  transcriptOpen: boolean;
  onTranscriptToggle: () => void;
  onEnd: () => void;
  viewport: ViewportState;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetViewport: () => void;
}) {
  const { state } = useVoiceAssistant();
  const { enabled: micEnabled, toggle: toggleMic } = useTrackToggle({
    source: Track.Source.Microphone,
  });

  const label =
    state === "speaking"
      ? "Tutor is speaking…"
      : state === "thinking"
      ? "Thinking…"
      : state === "listening"
      ? "Listening…"
      : "Connecting…";

  return (
    <VoiceFooter
      className={micEnabled ? "" : "muted"}
      viewport={viewport}
      onZoomIn={onZoomIn}
      onZoomOut={onZoomOut}
      onResetViewport={onResetViewport}
    >
      <div className="wrap">
        <div className="state">
          <Bars />
          {label}
        </div>
        <TranscriptButton
          open={transcriptOpen}
          onToggle={onTranscriptToggle}
        />
        <button
          className="icon-btn"
          onClick={() => toggleMic()}
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
    </VoiceFooter>
  );
}

function PlaceholderComposer({
  status,
  transcriptOpen,
  onTranscriptToggle,
  onEnd,
  viewport,
  onZoomIn,
  onZoomOut,
  onResetViewport,
}: {
  status: "connecting" | "disconnected";
  transcriptOpen: boolean;
  onTranscriptToggle: () => void;
  onEnd: () => void;
  viewport: ViewportState;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetViewport: () => void;
}) {
  return (
    <VoiceFooter
      className={status}
      viewport={viewport}
      onZoomIn={onZoomIn}
      onZoomOut={onZoomOut}
      onResetViewport={onResetViewport}
    >
      <div className="wrap">
        <div className="state">
          <Bars />
          {status === "connecting" ? "Connecting…" : "Disconnected"}
        </div>
        <TranscriptButton
          open={transcriptOpen}
          onToggle={onTranscriptToggle}
        />
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
    </VoiceFooter>
  );
}

function TranscriptButton({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      className={`transcript-toggle ${open ? "active" : ""}`}
      onClick={onToggle}
      aria-label={open ? "Hide transcript" : "Open transcript"}
      aria-pressed={open}
    >
      Transcript
    </button>
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
