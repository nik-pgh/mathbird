import { X } from "lucide-react";
import { documentFileUrl } from "../../lib/api";
import { CANVAS_WHEEL_IGNORE_ATTR } from "../../lib/canvasViewport";
import type { TextbookDisplayMode } from "../../lib/pdfWorkspaceLayout";

interface Props {
  docId: string | null;
  title: string | null;
  displayMode: TextbookDisplayMode;
  onClose?: () => void;
}

function textbookEmbedUrl(docId: string): string {
  const base = documentFileUrl(docId);
  return `${base}#toolbar=0&navpanes=0&view=FitH&zoom=page-width`;
}

export default function TextbookOverlay({
  docId,
  title,
  displayMode,
  onClose,
}: Props) {
  if (!docId || displayMode === "hidden" || displayMode === "collapsed") return null;

  const src = textbookEmbedUrl(docId);
  const isOverlay = displayMode === "overlay";
  const stopBoardWheel = (event: React.WheelEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  return (
    <section
      {...{ [CANVAS_WHEEL_IGNORE_ATTR]: "" }}
      className={`textbook-overlay textbook-overlay-viewer ${
        isOverlay ? "textbook-overlay-mobile" : "textbook-overlay-docked"
      }`}
      aria-label="Textbook"
      onWheel={stopBoardWheel}
    >
      {isOverlay && onClose && (
        <button
          type="button"
          className="textbook-overlay-close"
          onClick={onClose}
          aria-label="Close textbook"
          title="Close textbook"
        >
          <X size={17} aria-hidden="true" />
        </button>
      )}
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
