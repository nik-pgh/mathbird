/**
 * Draggable, resizable floating PDF window for the session page.
 *
 * Mounted by ``SessionPage`` when ``pdfOpen`` is true and an ``activeDocId``
 * is known. Renders the PDF in a native ``<iframe>`` against
 * ``GET /api/documents/{id}/file``. Position + size are persisted to
 * localStorage so reopening restores the user's last layout.
 *
 * Drag handle = the header; resize handle = bottom-right corner. On viewports
 * narrower than 900px the popover becomes a full-screen sheet (drag/resize
 * disabled by CSS).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { documentFileUrl } from "../../lib/api";

const GEOM_KEY = "mathbird:pdf_popover_geom";
const MIN_W = 320;
const MIN_H = 400;

interface Geom {
  x: number;
  y: number;
  w: number;
  h: number;
}

const DEFAULT_GEOM: Geom = { x: 16, y: 64, w: 520, h: 720 };

function loadGeom(): Geom {
  try {
    const raw = window.localStorage.getItem(GEOM_KEY);
    if (!raw) return DEFAULT_GEOM;
    const parsed = JSON.parse(raw);
    if (
      typeof parsed?.x === "number" &&
      typeof parsed?.y === "number" &&
      typeof parsed?.w === "number" &&
      typeof parsed?.h === "number"
    ) {
      return parsed as Geom;
    }
  } catch {
    /* fall through */
  }
  return DEFAULT_GEOM;
}

function saveGeom(g: Geom): void {
  try {
    window.localStorage.setItem(GEOM_KEY, JSON.stringify(g));
  } catch {
    /* ignore */
  }
}

interface Props {
  docId: string;
  title?: string;
  onClose: () => void;
}

export default function PdfPopover({ docId, title, onClose }: Props) {
  const [geom, setGeom] = useState<Geom>(() => loadGeom());
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);
  const resizeStart = useRef<{ x: number; y: number; w: number; h: number } | null>(
    null,
  );
  const geomRef = useRef<Geom>(geom);
  geomRef.current = geom;

  // Persist geometry on every change. Pointer drag fires many state updates,
  // but localStorage writes are cheap enough at this rate (single small JSON
  // object) that debouncing isn't worth the complexity.
  useEffect(() => {
    saveGeom(geom);
  }, [geom]);

  // Close on Esc.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const onHeaderPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if ((e.target as HTMLElement).closest("button")) return; // don't drag from close button
      const g = geomRef.current;
      dragOffset.current = { dx: e.clientX - g.x, dy: e.clientY - g.y };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [],
  );
  const onHeaderPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragOffset.current) return;
      setGeom((g) => ({
        ...g,
        x: Math.max(0, e.clientX - dragOffset.current!.dx),
        y: Math.max(0, e.clientY - dragOffset.current!.dy),
      }));
    },
    [],
  );
  const onHeaderPointerUp = useCallback(() => {
    dragOffset.current = null;
  }, []);

  const onResizePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.stopPropagation();
      const g = geomRef.current;
      resizeStart.current = {
        x: e.clientX,
        y: e.clientY,
        w: g.w,
        h: g.h,
      };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [],
  );
  const onResizePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!resizeStart.current) return;
      const dx = e.clientX - resizeStart.current.x;
      const dy = e.clientY - resizeStart.current.y;
      setGeom((g) => ({
        ...g,
        w: Math.max(MIN_W, Math.min(window.innerWidth * 0.8, resizeStart.current!.w + dx)),
        h: Math.max(MIN_H, Math.min(window.innerHeight * 0.9, resizeStart.current!.h + dy)),
      }));
    },
    [],
  );
  const onResizePointerUp = useCallback(() => {
    resizeStart.current = null;
  }, []);

  const src = `${documentFileUrl(docId)}#toolbar=0&navpanes=0`;

  return (
    <div
      className="pdf-popover"
      role="dialog"
      aria-label={title ?? "PDF viewer"}
      style={{
        left: geom.x,
        top: geom.y,
        width: geom.w,
        height: geom.h,
      }}
    >
      <div
        className="pdf-popover-head"
        onPointerDown={onHeaderPointerDown}
        onPointerMove={onHeaderPointerMove}
        onPointerUp={onHeaderPointerUp}
        onPointerCancel={onHeaderPointerUp}
      >
        <span className="pdf-popover-title">{title ?? "PDF"}</span>
        <button className="pdf-popover-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <iframe className="pdf-popover-frame" src={src} title={title ?? "PDF"} />
      <div
        className="pdf-popover-resize"
        onPointerDown={onResizePointerDown}
        onPointerMove={onResizePointerMove}
        onPointerUp={onResizePointerUp}
        onPointerCancel={onResizePointerUp}
        aria-hidden="true"
      />
    </div>
  );
}
