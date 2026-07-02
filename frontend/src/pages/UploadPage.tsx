import { useCallback, useEffect, useState } from "react";
import PdfDropZone from "../components/PdfDropZone";
import ProgressRow, { UploadStage } from "../components/library/ProgressRow";
import DocList from "../components/library/DocList";
import SessionTopbar from "../components/session/SessionTopbar";
import {
  UploadedDocument,
  ingestDocument,
  listDocuments,
  uploadPdf,
  waitForDocumentReady,
} from "../lib/api";
import {
  clearActiveDocId,
  getActiveDocId,
  setActiveDocId,
  subscribeActiveDocId,
} from "../lib/activeDoc";

interface UploadJob {
  tmpId: string;
  name: string;
  file: File;
  stage: UploadStage;
  error?: string | null;
  docId?: string;
}

export default function UploadPage() {
  const [docs, setDocs] = useState<UploadedDocument[]>([]);
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const [activeDocId, setActiveDocIdState] = useState<string | null>(() =>
    getActiveDocId(),
  );
  const [reindexingDocId, setReindexingDocId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDocuments()
      .then((list) => {
        setDocs(list);
        const stored = getActiveDocId();
        if (stored && !list.some((d) => d.doc_id === stored)) {
          clearActiveDocId();
          setActiveDocIdState(null);
        }
      })
      .catch((e) => setError(String(e)));

    const poll = window.setInterval(() => {
      listDocuments()
        .then(setDocs)
        .catch((e) => setError(String(e)));
    }, 3000);

    return () => window.clearInterval(poll);
  }, []);

  useEffect(() => subscribeActiveDocId(setActiveDocIdState), []);

  const updateJob = useCallback(
    (tmpId: string, patch: Partial<UploadJob>) =>
      setJobs((prev) =>
        prev.map((j) => (j.tmpId === tmpId ? { ...j, ...patch } : j)),
      ),
    [],
  );

  const removeJob = useCallback(
    (tmpId: string) => setJobs((prev) => prev.filter((j) => j.tmpId !== tmpId)),
    [],
  );

  const runJob = useCallback(
    async (job: UploadJob) => {
      try {
        updateJob(job.tmpId, { stage: "uploading", error: null });
        const uploaded = await uploadPdf(job.file);
        updateJob(job.tmpId, { stage: "indexing", docId: uploaded.doc_id });

        await ingestDocument(uploaded.doc_id);
        const indexed = await waitForDocumentReady(uploaded.doc_id, {
          intervalMs: 500,
        });
        // Job complete: prepend the document and drop the row.
        setDocs((prev) => [indexed, ...prev]);
        removeJob(job.tmpId);
      } catch (e) {
        updateJob(job.tmpId, { stage: "error", error: String(e) });
      }
    },
    [removeJob, updateJob],
  );

  const handleFiles = useCallback(
    (files: File[]) => {
      setError(null);
      const created: UploadJob[] = files.map((file) => ({
        tmpId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        file,
        stage: "uploading",
      }));
      setJobs((prev) => [...created, ...prev]);
      created.forEach(runJob);
    },
    [runJob],
  );

  const handleSelect = useCallback((docId: string) => {
    setActiveDocId(docId);
    setActiveDocIdState(docId);
  }, []);

  const handleReindex = useCallback(async (docId: string) => {
    setReindexingDocId(docId);
    try {
      await ingestDocument(docId);
      const indexed = await waitForDocumentReady(docId, { intervalMs: 500 });
      setDocs((prev) => prev.map((d) => (d.doc_id === docId ? indexed : d)));
    } catch (e) {
      setError(String(e));
    } finally {
      setReindexingDocId(null);
    }
  }, []);

  const handleRetry = useCallback(
    (tmpId: string) => {
      const job = jobs.find((j) => j.tmpId === tmpId);
      if (!job) return;
      runJob(job);
    },
    [jobs, runJob],
  );

  const uploading = jobs.some(
    (j) => j.stage === "uploading" || j.stage === "indexing",
  );

  return (
    <>
      <SessionTopbar />
      <main>
        <section className="library-page">
          <header className="page-header">
            <h1>Library</h1>
            <p>Drop PDFs to give the tutor context. Pick one to use this session.</p>
          </header>

          <PdfDropZone onFiles={handleFiles} disabled={uploading} />

          {error && <div className="error">{error}</div>}

          {jobs.length > 0 && (
            <section className="upload-jobs">
              <h2>In progress</h2>
              <ul>
                {jobs.map((j) => (
                  <ProgressRow
                    key={j.tmpId}
                    name={j.name}
                    stage={j.stage}
                    error={j.error}
                    onRetry={
                      j.stage === "error" ? () => handleRetry(j.tmpId) : undefined
                    }
                  />
                ))}
              </ul>
            </section>
          )}

          <section className="doc-list-section">
            <h2>Indexed ({docs.filter((d) => d.status === "indexed").length})</h2>
            <DocList
              docs={docs}
              activeDocId={activeDocId}
              onSelect={handleSelect}
              onReindex={handleReindex}
              reindexingDocId={reindexingDocId}
            />
          </section>
        </section>
      </main>
    </>
  );
}
