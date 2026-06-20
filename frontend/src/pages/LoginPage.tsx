import { googleLoginUrl } from "../lib/auth";

export default function LoginPage() {
  return (
    <main className="login-page">
      <div className="login-card">
        <h1>MathBird</h1>
        <p>Sign in to upload textbooks and start a tutoring session.</p>
        <a className="login-google-btn" href={googleLoginUrl()}>
          Sign in with Google
        </a>
      </div>
    </main>
  );
}
