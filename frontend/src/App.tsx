import { Route, Routes, useSearchParams } from "react-router-dom";
import AuthGate from "./components/auth/AuthGate";
import EvalDashboardPage from "./pages/EvalDashboardPage";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";
import SessionPage from "./pages/SessionPage";

const evalsEnabled = import.meta.env.VITE_EVALS_ENABLED === "true";

/** Wrap /session with AuthGate unless the guest query param is present. */
function SessionRoute() {
  const [params] = useSearchParams();
  const isGuest = params.get("guest") === "true";
  if (isGuest) return <SessionPage />;
  return (
    <AuthGate>
      <SessionPage />
    </AuthGate>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <AuthGate>
              <UploadPage />
            </AuthGate>
          }
        />
        {evalsEnabled ? (
          <Route
            path="/evals"
            element={
              <AuthGate>
                <EvalDashboardPage />
              </AuthGate>
            }
          />
        ) : null}
        <Route path="/session" element={<SessionRoute />} />
      </Routes>
    </div>
  );
}
