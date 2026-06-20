import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchDocumentPdfBlob } from "../../lib/api";
import { CANVAS_WHEEL_IGNORE_ATTR } from "../../lib/canvasViewport";
import type { TextbookDisplayMode } from "../../lib/pdfWorkspaceLayout";

interface Props {
  docId: string | null;
  title: string | null;
  displayMode: TextbookDisplayMode;
  onClose?: () => void;
}

export default function TextbookOverlay({
  docId,
  title,
  displayMode,
  onClose,
}: Props) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!docId || displayMode === "hidden" || displayMode === "collapsed") {
      setSrc(null);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    fetchDocumentPdfBlob(docId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(`${url}#toolbar=0&navpanes=0&view=FitH&zoom=page-width`);
      })
      .catch(() => setSrc(null));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [docId, displayMode]);

  if (!docId || displayMode === "hidden" || displayMode === "collapsed") {
    return null;
  }

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
        {src ? (
          <iframe
            className="textbook-overlay-frame"
            src={src}
            title={title ?? "Textbook"}
          />
        ) : (
          <p className="textbook-overlay-loading">Loading textbook…</p>
        )}
      </div>
    </section>
  );
}
