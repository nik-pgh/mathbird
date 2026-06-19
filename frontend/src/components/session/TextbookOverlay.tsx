import { documentFileUrl } from "../../lib/api";
import type { TextbookDisplayMode } from "../../lib/pdfWorkspaceLayout";

interface Props {
  docId: string | null;
  title: string | null;
  displayMode: TextbookDisplayMode;
}

function textbookEmbedUrl(docId: string): string {
  const base = documentFileUrl(docId);
  return `${base}#toolbar=0&navpanes=0&view=FitH&zoom=page-width`;
}

export default function TextbookOverlay({
  docId,
  title,
  displayMode,
}: Props) {
  if (!docId || displayMode === "hidden" || displayMode === "collapsed") return null;

  const src = textbookEmbedUrl(docId);
  const isOverlay = displayMode === "overlay";
  return (
    <section
      className={`textbook-overlay textbook-overlay-viewer ${
        isOverlay ? "textbook-overlay-mobile" : "textbook-overlay-docked"
      }`}
      aria-label="Textbook"
    >
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
