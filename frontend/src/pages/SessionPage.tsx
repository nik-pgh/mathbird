import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import {
  UploadedDocument,
  listDocuments,
  requestToken,
} from "../lib/api";
import { getActiveDocId } from "../lib/activeDoc";
import SessionTopbar from "../components/session/SessionTopbar";
import SharedReasoningWorkspace from "../components/session/SharedReasoningWorkspace";
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
  const [activeDoc, setActiveDoc] = useState<UploadedDocument | null>(null);

  const activeDocId = useMemo(() => getActiveDocId(), []);

  // Resolve filename for the textbook overlay title.
  useEffect(() => {
    if (!activeDocId) return;
    listDocuments()
      .then((list) => {
        const found = list.find((d) => d.doc_id === activeDocId) ?? null;
        setActiveDoc(found);
      })
      .catch(() => {
        /* non-fatal — popover still works without a filename */
      });
  }, [activeDocId]);

  const connect = useCallback(async () => {
    setError(null);
    setStatus("connecting");
    try {
      const t = await requestToken(
        activeDocId ? { doc_id: activeDocId } : undefined,
      );
      setConn({ url: t.url, token: t.token, room: t.room });
    } catch (e) {
      setError(String(e));
      setStatus("disconnected");
    }
  }, [activeDocId]);

  useEffect(() => {
    connect();
  }, [connect]);

  const handleEnd = useCallback(() => {
    setConn(null);
    navigate("/");
  }, [navigate]);

  const handleUnexpectedDisconnect = useCallback(() => {
    setStatus("disconnected");
    setError("Lost connection to the tutor.");
    setConn(null);
  }, []);

  const filename = useMemo(() => {
    if (!activeDoc) return null;
    const parts = activeDoc.key.split("/");
    return parts[parts.length - 1] || activeDoc.doc_id;
  }, [activeDoc]);

  return (
    <>
      <SessionTopbar session={{ status, label: "Session" }} />
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
          {error && (
            <div className="session-error">
              <span>{error}</span>
              <button className="retry" onClick={connect}>
                Retry
              </button>
            </div>
          )}
          <SharedReasoningWorkspace
            status={status}
            activeDocId={activeDocId}
            filename={filename}
            onEnd={handleEnd}
          />
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
