import { UploadedDocument } from "../../lib/api";

interface Props {
  docs: UploadedDocument[];
  activeDocId: string | null;
  onSelect: (docId: string) => void;
  onReindex: (docId: string) => void;
  reindexingDocId?: string | null;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function filenameOf(doc: UploadedDocument): string {
  const parts = doc.key.split("/");
  return parts[parts.length - 1] || doc.doc_id;
}

export default function DocList({
  docs,
  activeDocId,
  onSelect,
  onReindex,
  reindexingDocId,
}: Props) {
  if (docs.length === 0) {
    return <p className="empty">No documents yet.</p>;
  }
  return (
    <ul className="doc-list">
      {docs.map((d) => {
        const indexed = d.status === "indexed";
        const isActive = activeDocId === d.doc_id;
        const isReindexing = reindexingDocId === d.doc_id;
        return (
          <li key={d.doc_id} className={`doc-row ${indexed ? "indexed" : "unindexed"}`}>
            <label className="doc-pick">
              <input
                type="radio"
                name="active-doc"
                checked={isActive}
                disabled={!indexed}
                onChange={() => onSelect(d.doc_id)}
              />
              <span className="doc-name">{filenameOf(d)}</span>
            </label>
            <span className="doc-meta">{formatBytes(d.size)}</span>
            <span className={`doc-status ${d.status}`}>{d.status}</span>
            <span className="doc-action">
              {!indexed && (
                <button
                  className="reindex"
                  disabled={isReindexing}
                  onClick={() => onReindex(d.doc_id)}
                >
                  {isReindexing ? "Indexing..." : "Re-index"}
                </button>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
