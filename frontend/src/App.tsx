import { Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import SessionPage from "./pages/SessionPage";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/session" element={<SessionPage />} />
      </Routes>
    </div>
  );
}
