import { lazy, Suspense } from "react";
import { Route, Routes, useSearchParams } from "react-router-dom";
import AuthGate from "./components/auth/AuthGate";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";

const evalsEnabled = import.meta.env.VITE_EVALS_ENABLED === "true";

const SessionPage = lazy(() => import("./pages/SessionPage"));
const EvalDashboardPage = lazy(() => import("./pages/EvalDashboardPage"));

function RouteFallback() {
  return (
    <main className="route-fallback" aria-busy="true">
      Loading…
    </main>
  );
}

/** Wrap /session with AuthGate unless the guest query param is present. */
function SessionRoute() {
  const [params] = useSearchParams();
  const isGuest = params.get("guest") === "true";
  const page = (
    <Suspense fallback={<RouteFallback />}>
      <SessionPage />
    </Suspense>
  );
  if (isGuest) return page;
  return <AuthGate>{page}</AuthGate>;
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
                <Suspense fallback={<RouteFallback />}>
                  <EvalDashboardPage />
                </Suspense>
              </AuthGate>
            }
          />
        ) : null}
        <Route path="/session" element={<SessionRoute />} />
      </Routes>
    </div>
  );
}
