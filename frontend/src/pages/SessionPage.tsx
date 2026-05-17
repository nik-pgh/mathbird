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
          onDisconnected={handleEnd}
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
        <SessionSkeleton
          error={error}
          status={status}
          onRetry={connect}
          onEnd={handleEnd}
        />
      )}
    </>
  );
}

function SessionSkeleton({
  error,
  status,
  onRetry,
  onEnd,
}: {
  error: string | null;
  status: Status;
  onRetry: () => void;
  onEnd: () => void;
}) {
  return (
    <section className="session-room">
      <div className="session-conv">
        <div className="transcript empty">
          <p>
            {error
              ? "Couldn't connect to your tutor."
              : "Connecting to your tutor…"}
          </p>
        </div>
        {error && (
          <div className="session-error">
            <span>{error}</span>
            <button className="retry" onClick={onRetry}>
              Retry
            </button>
          </div>
        )}
        <VoiceComposer status={status} onEnd={onEnd} />
      </div>
      <div className="session-boards">
        <div className="board tutor-board">
          <div className="head">
            <span className="label">Tutor board</span>
            <span className="spacer" />
          </div>
          <div className="surface">
            <div
              className="empty"
              style={{
                margin: "auto",
                textAlign: "center",
                color: "var(--text-3)",
                fontSize: 13,
              }}
            >
              {error ? "Retry to reconnect." : "Connecting…"}
            </div>
          </div>
        </div>
        <div className="board user-board">
          <div className="head">
            <span className="label">Your pad</span>
            <span className="spacer" />
          </div>
          <div className="surface" />
        </div>
      </div>
    </section>
  );
}
