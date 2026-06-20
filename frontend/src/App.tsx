import { Route, Routes } from "react-router-dom";
import AuthGate from "./components/auth/AuthGate";
import EvalDashboardPage from "./pages/EvalDashboardPage";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";
import SessionPage from "./pages/SessionPage";

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
        <Route path="/evals" element={<EvalDashboardPage />} />
        <Route
          path="/session"
          element={
            <AuthGate>
              <SessionPage />
            </AuthGate>
          }
        />
      </Routes>
    </div>
  );
}
