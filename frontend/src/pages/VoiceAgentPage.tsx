import { useCallback, useState } from "react";
import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
} from "@livekit/components-react";
import { requestToken } from "../lib/api";
import Transcript from "../components/Transcript";

interface Connection {
  url: string;
  token: string;
  room: string;
}

export default function VoiceAgentPage() {
  const [conn, setConn] = useState<Connection | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(async () => {
    setError(null);
    setConnecting(true);
    try {
      const t = await requestToken();
      setConn({ url: t.url, token: t.token, room: t.room });
    } catch (e) {
      setError(String(e));
    } finally {
      setConnecting(false);
    }
  }, []);

  const disconnect = useCallback(() => setConn(null), []);

  if (!conn) {
    return (
      <section className="page voice-page">
        <header className="page-header">
          <h1>Voice agent</h1>
          <p>
            Connect to start a voice conversation. The agent will join the room
            automatically.
          </p>
        </header>

        <button className="primary-button" onClick={connect} disabled={connecting}>
          {connecting ? "Connecting…" : "Start conversation"}
        </button>

        {error && <div className="error">{error}</div>}
      </section>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={conn.url}
      token={conn.token}
      connect
      audio
      video={false}
      onDisconnected={disconnect}
      className="voice-room"
    >
      <VoiceAgentInner roomName={conn.room} onLeave={disconnect} />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function VoiceAgentInner({
  roomName,
  onLeave,
}: {
  roomName: string;
  onLeave: () => void;
}) {
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <section className="page voice-page">
      <header className="page-header">
        <h1>Voice agent</h1>
        <p className="room-meta">
          Room: <code>{roomName}</code> · Agent: <code>{state}</code>
        </p>
      </header>

      <div className="visualizer">
        <BarVisualizer state={state} barCount={24} trackRef={audioTrack} />
      </div>

      <Transcript />

      <button className="secondary-button" onClick={onLeave}>
        End conversation
      </button>
    </section>
  );
}
