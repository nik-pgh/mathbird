import { useCallback, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { logout } from "../../lib/api";
import { evalsEnabled } from "../../lib/features";
import { exitGuestMode, isGuestMode } from "../../lib/guestMode";
import { useSessionToolbarContent } from "./SessionToolbarContext";

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
  const toolbarContent = useSessionToolbarContent();
  const [signingOut, setSigningOut] = useState(false);
  const guest = isGuestMode();

  const handleSignOut = useCallback(async () => {
    setSigningOut(true);
    try {
      if (guest) {
        exitGuestMode();
        navigate("/login");
        return;
      }
      await logout();
      navigate("/login");
    } catch {
      navigate("/login");
    } finally {
      setSigningOut(false);
    }
  }, [guest, navigate]);

  if (session) {
    return (
      <header className="topbar topbar--session">
        <Link to="/" className="brand topbar-session-start">
          mathbird
        </Link>
        <div className="topbar-session-center">{toolbarContent}</div>
        <div className="topbar-session-end">
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
        </div>
      </header>
    );
  }

  return (
    <header className="topbar">
      <Link to="/" className="brand">
        mathbird
      </Link>
      <nav className="topbar-nav" aria-label="Primary navigation">
        <Link className={onLibrary ? "active" : ""} to="/">
          Library
        </Link>
        {evalsEnabled ? (
          <Link
            className={location.pathname === "/evals" ? "active" : ""}
            to="/evals"
          >
            Evals
          </Link>
        ) : null}
      </nav>
      <div className="spacer" />

      <button
        type="button"
        className="btn"
        onClick={() => void handleSignOut()}
        disabled={signingOut}
      >
        {signingOut ? "Signing out…" : guest ? "Exit guest" : "Sign out"}
      </button>
      <button
        className="btn primary"
        onClick={() => navigate("/session")}
      >
        <span className="btn-label-full">Start session →</span>
        <span className="btn-label-short">Start</span>
      </button>
    </header>
  );
}
