import { Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import VoiceAgentPage from "./pages/VoiceAgentPage";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/session" element={<VoiceAgentPage />} />
      </Routes>
    </div>
  );
}
