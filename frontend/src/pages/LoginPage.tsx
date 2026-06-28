import { useNavigate } from "react-router-dom";
import { GUEST_ENABLED, googleLoginUrl } from "../lib/auth";

export default function LoginPage() {
  const navigate = useNavigate();

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
            <button
              className="login-guest-btn"
              onClick={() => navigate("/session?guest=true")}
            >
              Try as guest
            </button>
            <p className="login-guest-hint">
              Jump straight into a voice session with a sample textbook.
              No account needed — progress won't be saved.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
