import { lazy, Suspense } from "react";
import { Route, Routes, useSearchParams } from "react-router-dom";
import AuthGate from "./components/auth/AuthGate";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";

import { evalsEnabled } from "./lib/features";
import { syncGuestModeFromSearchParams } from "./lib/guestMode";

const SessionPage = lazy(() => import("./pages/SessionPage"));
const EvalDashboardPage = lazy(() => import("./pages/EvalDashboardPage"));

function RouteFallback() {
  return (
    <main className="route-fallback" aria-busy="true">
      Loading…
    </main>
  );
}

/** Sync `?guest=true` once at the app shell; AuthGate reads sessionStorage. */
function GuestModeSync() {
  const [params] = useSearchParams();
  syncGuestModeFromSearchParams(params);
  return null;
}

function SessionRoute() {
  return (
    <AuthGate>
      <Suspense fallback={<RouteFallback />}>
        <SessionPage />
      </Suspense>
    </AuthGate>
  );
}

/** Wrap /evals with AuthGate unless `?embed=true` (guest bypass is inside AuthGate). */
function EvalRoute() {
  const [params] = useSearchParams();
  const isEmbedded = params.get("embed") === "true";
  const page = (
    <Suspense fallback={<RouteFallback />}>
      <EvalDashboardPage isEmbedded={isEmbedded} />
    </Suspense>
  );
  if (isEmbedded) return page;
  return <AuthGate>{page}</AuthGate>;
}

export default function App() {
  return (
    <div className="app-shell">
      <GuestModeSync />
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
          <Route path="/evals" element={<EvalRoute />} />
        ) : null}
        <Route path="/session" element={<SessionRoute />} />
      </Routes>
    </div>
  );
}
