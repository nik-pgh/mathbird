import { Route, Routes } from "react-router-dom";
import EvalDashboardPage from "./pages/EvalDashboardPage";
import UploadPage from "./pages/UploadPage";
import SessionPage from "./pages/SessionPage";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/evals" element={<EvalDashboardPage />} />
        <Route path="/session" element={<SessionPage />} />
      </Routes>
    </div>
  );
}
