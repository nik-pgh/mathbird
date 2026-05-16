import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PdfDropZone from "../components/PdfDropZone";
import { UploadedDocument, listDocuments, uploadPdf } from "../lib/api";

export default function UploadPage() {
  const [docs, setDocs] = useState<UploadedDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDocuments()
      .then(setDocs)
      .catch((e) => setError(String(e)));
  }, []);

  async function handleFiles(files: File[]) {
    setError(null);
    setUploading(true);
    try {
      const uploaded = await Promise.all(files.map(uploadPdf));
      setDocs((prev) => [...uploaded, ...prev]);
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="page upload-page">
      <header className="page-header">
        <h1>Upload documents</h1>
        <p>Drop PDFs to make them available to the voice agent.</p>
      </header>

      <PdfDropZone onFiles={handleFiles} disabled={uploading} />

      {error && <div className="error">{error}</div>}

      <section className="doc-list">
        <div className="doc-list-header">
          <h2>Indexed documents ({docs.length})</h2>
          <Link to="/voice" className="primary-link">
            Talk to the agent →
          </Link>
        </div>
        {docs.length === 0 ? (
          <p className="empty">No documents yet.</p>
        ) : (
          <ul>
            {docs.map((d) => (
              <li key={d.key}>
                <span className="doc-name">{d.key.split("/").pop()}</span>
                <span className="doc-meta">{formatBytes(d.size)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
