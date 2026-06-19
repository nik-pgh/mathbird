import { Link, useLocation, useNavigate } from "react-router-dom";

/** Top bar shared by both routes. Pass `session` to render session-mode controls. */
interface Props {
  /** Optional session-side props. When present, render session status. */
  session?: {
    status: "connecting" | "connected" | "disconnected";
    label?: string; // e.g. "Quadratics · 04:12"; defaults to "Session"
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
      {!session && (
        <nav className="topbar-nav" aria-label="Primary navigation">
          <Link className={onLibrary ? "active" : ""} to="/">
            Library
          </Link>
          <Link
            className={location.pathname === "/evals" ? "active" : ""}
            to="/evals"
          >
            Evals
          </Link>
        </nav>
      )}
      <div className="spacer" />

      {session ? (
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
      ) : (
        <button
          className="btn primary"
          onClick={() => navigate("/session")}
        >
          <span className="btn-label-full">Start session →</span>
          <span className="btn-label-short">Start</span>
        </button>
      )}
    </header>
  );
}
