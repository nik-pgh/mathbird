import { FileText, X } from "lucide-react";
import { documentFileUrl } from "../../lib/api";
import type { TextbookDisplayMode } from "../../lib/pdfWorkspaceLayout";

interface Props {
  docId: string | null;
  title: string | null;
  displayMode: TextbookDisplayMode;
  onToggle: () => void;
}

function textbookEmbedUrl(docId: string): string {
  const base = documentFileUrl(docId);
  return `${base}#navpanes=0&view=FitH&zoom=page-width`;
}

export default function TextbookOverlay({
  docId,
  title,
  displayMode,
  onToggle,
}: Props) {
  if (!docId || displayMode === "hidden") return null;

  if (displayMode === "collapsed") {
    return (
      <button
        type="button"
        className="textbook-control-button"
        onClick={onToggle}
        aria-label={`Open textbook${title ? `: ${title}` : ""}`}
        title={title ?? "Open textbook"}
      >
        <FileText size={20} aria-hidden="true" />
      </button>
    );
  }

  const src = textbookEmbedUrl(docId);
  const isOverlay = displayMode === "overlay";
  return (
    <section
      className={`textbook-overlay textbook-overlay-viewer ${
        isOverlay ? "textbook-overlay-mobile" : "textbook-overlay-docked"
      }`}
      aria-label="Textbook"
    >
      <header className="textbook-overlay-head">
        <span>{title ?? "Textbook"}</span>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Minimize textbook"
          title="Minimize textbook"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </header>
      <div className="textbook-overlay-body">
        <iframe
          className="textbook-overlay-frame"
          src={src}
          title={title ?? "Textbook"}
        />
      </div>
    </section>
  );
}
