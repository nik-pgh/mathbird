import { useNavigate } from "react-router-dom";
import { GUEST_ENABLED, googleLoginUrl } from "../lib/api";
import { enterGuestMode } from "../lib/guestMode";

export default function LoginPage() {
  const navigate = useNavigate();

  const handleGuest = () => {
    enterGuestMode();
    navigate("/");
  };

  return (
    <main className="login-page">
      <div className="login-card">
        <h1>MathBird</h1>
        <p>Sign in to upload textbooks and start a tutoring session.</p>
        <a className="login-google-btn" href={googleLoginUrl()}>
          Sign in with Google
        </a>
        {GUEST_ENABLED && (
          <>
            <div className="login-divider">
              <span>or</span>
            </div>
            <button className="login-guest-btn" onClick={handleGuest}>
              Try as guest
            </button>
            <p className="login-guest-hint">
              Browse the sample library, explore eval dashboards, and start a
              voice session — no account needed. Progress won&apos;t be saved.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
