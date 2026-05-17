import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import { requestToken } from "../lib/api";
import SessionTopbar from "../components/session/SessionTopbar";
import VoiceComposer from "../components/session/VoiceComposer";
import Transcript from "../components/Transcript";
import AiBoard from "../components/whiteboard/AiBoard";
import UserBoard from "../components/whiteboard/UserBoard";
import "../styles/session.css";

interface Connection {
  url: string;
  token: string;
  room: string;
}

type Status = "connecting" | "connected" | "disconnected";

export default function SessionPage() {
  const navigate = useNavigate();
  const [conn, setConn] = useState<Connection | null>(null);
  const [status, setStatus] = useState<Status>("connecting");
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(async () => {
    setError(null);
    setStatus("connecting");
    try {
      const t = await requestToken();
      setConn({ url: t.url, token: t.token, room: t.room });
    } catch (e) {
      setError(String(e));
      setStatus("disconnected");
    }
  }, []);

  useEffect(() => {
    connect();
  }, [connect]);

  const handleEnd = useCallback(() => {
    setConn(null);
    navigate("/");
  }, [navigate]);

  const handleUnexpectedDisconnect = useCallback(() => {
    // Triggered when LiveKit closes without user action.
    // Stay on the page and surface the disconnected status; user can Retry or End.
    setStatus("disconnected");
    setError("Lost connection to the tutor.");
    setConn(null);
  }, []);

  return (
    <>
      <SessionTopbar
        session={{ status, label: "Session", onEnd: handleEnd }}
      />
      {conn ? (
        <LiveKitRoom
          serverUrl={conn.url}
          token={conn.token}
          connect
          audio
          video={false}
          onConnected={() => setStatus("connected")}
          onDisconnected={handleUnexpectedDisconnect}
          onError={(e) => {
            setError(e.message);
            setStatus("disconnected");
          }}
        >
          <section className="session-room">
            <div className="session-conv">
              <Transcript />
              {error && (
                <div className="session-error">
                  <span>{error}</span>
                  <button className="retry" onClick={connect}>
                    Retry
                  </button>
                </div>
              )}
              <VoiceComposer status={status} onEnd={handleEnd} />
            </div>
            <div className="session-boards">
              <AiBoard />
              <UserBoard />
            </div>
          </section>
          <RoomAudioRenderer />
        </LiveKitRoom>
      ) : (
        <SessionSkeleton error={error} onRetry={connect} />
      )}
    </>
  );
}

function SessionSkeleton({
  error,
  onRetry,
}: {
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <main className="session-loading">
      <p className="connecting-msg">
        {error ? "Couldn't connect to your tutor." : "Connecting to your tutor…"}
      </p>
      {error && (
        <div className="session-error">
          <span>{error}</span>
          <button className="retry" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
    </main>
  );
}
