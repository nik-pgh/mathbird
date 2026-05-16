import { Link, Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import VoiceAgentPage from "./pages/VoiceAgentPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          mathbird
        </Link>
        <nav>
          <Link to="/">Documents</Link>
          <Link to="/voice">Voice agent</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/voice" element={<VoiceAgentPage />} />
        </Routes>
      </main>
    </div>
  );
}
