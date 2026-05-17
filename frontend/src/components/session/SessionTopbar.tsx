import { Link, useLocation, useNavigate } from "react-router-dom";

/**
 * Single top bar shared by both routes. Right-side action is contextual:
 * - on `/` (library): "Start session →" navigates to /session
 * - on `/session`: status pill + "End session" button (which calls onEnd if
 *   provided, otherwise navigates back to /)
 */
interface Props {
  /** Optional session-side props. When present, render the End button. */
  session?: {
    status: "connecting" | "connected" | "disconnected";
    label?: string; // e.g. "Quadratics · 04:12"; defaults to "Session"
    onEnd: () => void;
  };
}

export default function SessionTopbar({ session }: Props) {
  const location = useLocation();
  const navigate = useNavigate();
  const onLibrary = location.pathname === "/";

  return (
    <header className="topbar">
      <Link to="/" className="brand">
        mathbird
      </Link>
      <div className="spacer" />

      {session ? (
        <>
          <span
            className={`pill ${
              session.status === "disconnected" ? "danger" : ""
            }`}
          >
            <span className="dot" />
            {session.status === "connecting"
              ? "Connecting…"
              : session.status === "disconnected"
              ? "Disconnected"
              : session.label ?? "Session"}
          </span>
          <button className="btn" onClick={session.onEnd}>
            End session
          </button>
        </>
      ) : onLibrary ? (
        <button
          className="btn primary"
          onClick={() => navigate("/session")}
        >
          Start session →
        </button>
      ) : null}
    </header>
  );
}
