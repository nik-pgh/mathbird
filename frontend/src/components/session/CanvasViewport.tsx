import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import {
  clientToWorld as toWorld,
  panBy,
  zoomAtPoint,
} from "../../lib/canvasViewport";
import type { ViewportState } from "./workspaceTypes";
import { CanvasViewportProvider } from "./CanvasViewportContext";

interface Props {
  boardRef: RefObject<HTMLDivElement | null>;
  viewport: ViewportState;
  onViewportChange: (viewport: ViewportState) => void;
  children: React.ReactNode;
}

type PanDragState = {
  pointerId: number;
  startX: number;
  startY: number;
  startPan: { x: number; y: number };
};

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

export default function CanvasViewport({
  boardRef,
  viewport,
  onViewportChange,
  children,
}: Props) {
  const viewportRef = useRef(viewport);
  viewportRef.current = viewport;

  const onViewportChangeRef = useRef(onViewportChange);
  onViewportChangeRef.current = onViewportChange;

  const panDragRef = useRef<PanDragState | null>(null);
  const [isSpacePan, setIsSpacePan] = useState(false);
  const spacePanRef = useRef(false);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat || isEditableTarget(e.target)) return;
      e.preventDefault();
      spacePanRef.current = true;
      setIsSpacePan(true);
    };

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      spacePanRef.current = false;
      setIsSpacePan(false);
      panDragRef.current = null;
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = board.getBoundingClientRect();
      const focalX = e.clientX - rect.left;
      const focalY = e.clientY - rect.top;
      const current = viewportRef.current;

      if (e.ctrlKey || e.metaKey) {
        const factor = e.deltaY > 0 ? 0.92 : 1.08;
        onViewportChangeRef.current(
          zoomAtPoint(current, current.zoom * factor, focalX, focalY),
        );
        return;
      }

      onViewportChangeRef.current(
        panBy(current, -e.deltaX, -e.deltaY),
      );
    };

    board.addEventListener("wheel", onWheel, { passive: false });
    return () => board.removeEventListener("wheel", onWheel);
  }, [boardRef]);

  const beginPan = useCallback(
    (pointerId: number, clientX: number, clientY: number) => {
      const current = viewportRef.current;
      panDragRef.current = {
        pointerId,
        startX: clientX,
        startY: clientY,
        startPan: { ...current.pan },
      };
    },
    [],
  );

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const onPointerDown = (e: PointerEvent) => {
      const isMiddle = e.button === 1;
      const isSpaceLeft = e.button === 0 && spacePanRef.current;
      if (!isMiddle && !isSpaceLeft) return;

      e.preventDefault();
      beginPan(e.pointerId, e.clientX, e.clientY);
      board.setPointerCapture(e.pointerId);
    };

    const onPointerMove = (e: PointerEvent) => {
      const drag = panDragRef.current;
      if (!drag || drag.pointerId !== e.pointerId) return;

      onViewportChangeRef.current({
        ...viewportRef.current,
        pan: {
          x: drag.startPan.x + (e.clientX - drag.startX),
          y: drag.startPan.y + (e.clientY - drag.startY),
        },
      });
    };

    const endPan = (e: PointerEvent) => {
      const drag = panDragRef.current;
      if (!drag || drag.pointerId !== e.pointerId) return;
      panDragRef.current = null;
    };

    board.addEventListener("pointerdown", onPointerDown);
    board.addEventListener("pointermove", onPointerMove);
    board.addEventListener("pointerup", endPan);
    board.addEventListener("pointercancel", endPan);
    return () => {
      board.removeEventListener("pointerdown", onPointerDown);
      board.removeEventListener("pointermove", onPointerMove);
      board.removeEventListener("pointerup", endPan);
      board.removeEventListener("pointercancel", endPan);
    };
  }, [boardRef, beginPan]);

  const clientToWorld = useCallback(
    (clientX: number, clientY: number) => {
      const board = boardRef.current;
      if (!board) {
        return { x: clientX, y: clientY };
      }
      return toWorld(clientX, clientY, board.getBoundingClientRect(), viewportRef.current);
    },
    [boardRef],
  );

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;
    board.classList.toggle("space-pan", isSpacePan);
    return () => board.classList.remove("space-pan");
  }, [boardRef, isSpacePan]);

  const contextValue = useMemo(
    () => ({
      viewport,
      isSpacePan,
      clientToWorld,
    }),
    [viewport, isSpacePan, clientToWorld],
  );

  const worldStyle = {
    transform: `translate(${viewport.pan.x}px, ${viewport.pan.y}px) scale(${viewport.zoom})`,
  };

  return (
    <CanvasViewportProvider value={contextValue}>
      <div
        className={`canvas-world ${isSpacePan ? "space-pan" : ""}`}
        style={worldStyle}
      >
        {children}
      </div>
    </CanvasViewportProvider>
  );
}
