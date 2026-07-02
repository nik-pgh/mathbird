import { memo, useCallback, useEffect, useRef, useState } from "react";
import { GripVertical } from "lucide-react";
import { getStroke } from "perfect-freehand";
import { useBoardChannel } from "../whiteboard/useBoardChannel";
import {
  USER_BOARD_TOPIC,
  type UserBoardSnapshot,
  decodeUserSnapshot,
  encodeUserSnapshot,
} from "../../lib/whiteboard";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import type { InkColor, InkTool, InkTarget } from "./workspaceTypes";

type InkCommand = {
  id: number;
  target: Extract<InkTarget, { kind: "student_card" }>;
  action: "undo" | "clear";
} | null;

interface Props {
  cardId: string;
  label: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  isCapturing: boolean;
  selected?: boolean;
  inkTool: InkTool;
  inkColor: InkColor;
  inkCommand: InkCommand;
  onMove: (cardId: string, position: { x: number; y: number }) => void;
  onResize: (cardId: string, size: { width: number; height: number }) => void;
  onRename: (cardId: string, label: string) => void;
  onCaptureStateChange: (cardId: string, value: boolean) => void;
  onStrokeTargeted: (target: Extract<InkTarget, { kind: "student_card" }>) => void;
  onSelect?: (cardId: string) => void;
}

const SNAPSHOT_INTERVAL_MS = 2000;
const MAX_LONG_EDGE = 512;
const CANVAS_BG = "#fffaf0";

type Point = [number, number, number];
type Stroke = { tool: InkTool; color: InkColor; points: Point[] };

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  startPosition: { x: number; y: number };
};

type ResizeState = {
  pointerId: number;
  startX: number;
  startY: number;
  startSize: { width: number; height: number };
};

function HandwritingPanel({
  cardId,
  label,
  position,
  size,
  isCapturing,
  selected = false,
  inkTool,
  inkColor,
  inkCommand,
  onMove,
  onResize,
  onRename,
  onCaptureStateChange,
  onStrokeTargeted,
  onSelect,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const positionRef = useRef(position);
  const sizeRef = useRef(size);
  const dragRef = useRef<DragState | null>(null);
  const resizeRef = useRef<ResizeState | null>(null);
  const snapshotTimerRef = useRef<number | null>(null);
  const snapshotVersionRef = useRef(0);
  const lastInkCommandIdRef = useRef<number | null>(null);
  const onCaptureStateChangeRef = useRef(onCaptureStateChange);
  const strokesRef = useRef<Stroke[]>([]);
  const drawingRef = useRef<Stroke | null>(null);
  const drawingPointerRef = useRef<number | null>(null);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [drawing, setDrawing] = useState<Stroke | null>(null);
  const [draftLabel, setDraftLabel] = useState(label);
  const { isSpacePan, clientToWorld, viewport } = useCanvasViewportContext();

  const { send } = useBoardChannel<
    typeof USER_BOARD_TOPIC,
    UserBoardSnapshot
  >({
    topic: USER_BOARD_TOPIC,
    decode: decodeUserSnapshot,
    encode: encodeUserSnapshot,
  });

  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  useEffect(() => {
    sizeRef.current = size;
  }, [size]);

  useEffect(() => {
    setDraftLabel(label);
  }, [label]);

  useEffect(() => {
    onCaptureStateChangeRef.current = onCaptureStateChange;
  }, [onCaptureStateChange]);

  useEffect(() => {
    strokesRef.current = strokes;
  }, [strokes]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = CANVAS_BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const allStrokes = drawing ? [...strokes, drawing] : strokes;
    for (const stroke of allStrokes) {
      drawStroke(ctx, stroke);
    }
  }, [strokes, drawing]);

  const sendEmptySnapshot = useCallback(async () => {
    snapshotVersionRef.current += 1;
    const version = snapshotVersionRef.current;
    if (snapshotTimerRef.current !== null) {
      window.clearTimeout(snapshotTimerRef.current);
      snapshotTimerRef.current = null;
    }

    onCaptureStateChangeRef.current(cardId, true);
    try {
      await send({
        png_b64: "",
        captured_at_ms: Date.now(),
        is_empty: true,
        card_id: cardId,
        card_label: label,
      });
    } finally {
      if (snapshotVersionRef.current === version) {
        onCaptureStateChangeRef.current(cardId, false);
      }
    }
  }, [cardId, label, send]);

  const scheduleSnapshot = useCallback(() => {
    snapshotVersionRef.current += 1;
    const version = snapshotVersionRef.current;
    onCaptureStateChangeRef.current(cardId, true);

    if (snapshotTimerRef.current !== null) {
      window.clearTimeout(snapshotTimerRef.current);
    }

    snapshotTimerRef.current = window.setTimeout(async () => {
      snapshotTimerRef.current = null;
      try {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const blob = await canvasToScaledPngBlob(canvas, MAX_LONG_EDGE);
        if (snapshotVersionRef.current !== version) return;
        if (!blob) return;
        const png_b64 = await blobToBase64(blob);
        if (snapshotVersionRef.current !== version) return;
        await send({
          png_b64,
          captured_at_ms: Date.now(),
          is_empty: false,
          card_id: cardId,
          card_label: label,
        });
      } finally {
        if (snapshotVersionRef.current === version) {
          onCaptureStateChangeRef.current(cardId, false);
        }
      }
    }, SNAPSHOT_INTERVAL_MS);
  }, [cardId, label, send]);

  useEffect(
    () => () => {
      snapshotVersionRef.current += 1;
      if (snapshotTimerRef.current !== null) {
        window.clearTimeout(snapshotTimerRef.current);
        snapshotTimerRef.current = null;
      }
      onCaptureStateChangeRef.current(cardId, false);
    },
    [cardId],
  );

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (e.button !== 0 || isSpacePan) return;
    if (drawingPointerRef.current !== null) return;

    const pt = pointerXY(e.currentTarget, e.nativeEvent);
    const nextDrawing = {
      tool: inkTool,
      color: inkColor,
      points: [[pt.x, pt.y, e.pressure || 0.5]] as Point[],
    };
    drawingRef.current = nextDrawing;
    drawingPointerRef.current = e.pointerId;
    setDrawing(nextDrawing);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (drawingPointerRef.current !== e.pointerId) return;
    const activeDrawing = drawingRef.current;
    if (!activeDrawing) return;

    const events = e.nativeEvent.getCoalescedEvents?.() ?? [e.nativeEvent];
    const nextPoints = events.map((event) => {
      const pt = pointerXY(e.currentTarget, event);
      return [pt.x, pt.y, event.pressure || 0.5] as Point;
    });
    const nextDrawing = {
      ...activeDrawing,
      points: [...activeDrawing.points, ...nextPoints],
    };
    drawingRef.current = nextDrawing;
    setDrawing(nextDrawing);
  };

  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (drawingPointerRef.current !== e.pointerId) return;
    const activeDrawing = drawingRef.current;
    if (!activeDrawing) return;

    setStrokes((prev) => {
      const next = [...prev, activeDrawing];
      strokesRef.current = next;
      return next;
    });
    drawingRef.current = null;
    drawingPointerRef.current = null;
    setDrawing(null);
    onStrokeTargeted({ kind: "student_card", cardId });
    scheduleSnapshot();
  };

  const undo = useCallback(() => {
    if (strokesRef.current.length === 0) return;

    const next = strokesRef.current.slice(0, -1);
    strokesRef.current = next;
    setStrokes(next);

    if (next.length === 0) {
      void sendEmptySnapshot();
    } else {
      scheduleSnapshot();
    }
  }, [sendEmptySnapshot, scheduleSnapshot]);

  const clear = useCallback(async () => {
    if (strokesRef.current.length === 0) return;

    strokesRef.current = [];
    setStrokes([]);
    await sendEmptySnapshot();
  }, [sendEmptySnapshot]);

  useEffect(() => {
    if (!inkCommand) return;
    if (inkCommand.target.kind !== "student_card") return;
    if (inkCommand.target.cardId !== cardId) return;
    if (lastInkCommandIdRef.current === inkCommand.id) return;

    lastInkCommandIdRef.current = inkCommand.id;
    if (inkCommand.action === "undo") {
      undo();
    } else {
      void clear();
    }
  }, [cardId, clear, inkCommand, undo]);

  const onDragHandlePointerDown = (e: React.PointerEvent<HTMLElement>) => {
    if (e.button !== 0 || isSpacePan) return;

    onSelect?.(cardId);
    const world = clientToWorld(e.clientX, e.clientY);
    dragRef.current = {
      pointerId: e.pointerId,
      startX: world.x,
      startY: world.y,
      startPosition: positionRef.current,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onDragHandlePointerMove = (e: React.PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;

    const world = clientToWorld(e.clientX, e.clientY);
    onMove(cardId, {
      x: drag.startPosition.x + (world.x - drag.startX),
      y: drag.startPosition.y + (world.y - drag.startY),
    });
  };

  const endDrag = (e: React.PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    dragRef.current = null;
  };

  const onResizePointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0) return;
    onSelect?.(cardId);
    resizeRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      startSize: sizeRef.current,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onResizePointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== e.pointerId) return;

    const widthDelta = (e.clientX - resize.startX) / viewport.zoom;
    const heightDelta = (e.clientY - resize.startY) / viewport.zoom / 0.75;
    const edgeDelta = Math.max(widthDelta, heightDelta);
    onResize(cardId, {
      width: resize.startSize.width + edgeDelta,
      height: (resize.startSize.width + edgeDelta) * 0.75,
    });
  };

  const endResize = (e: React.PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== e.pointerId) return;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    resizeRef.current = null;
  };

  return (
    <section
      className={`handwriting-panel ${isCapturing ? "capturing" : ""}${
        selected ? " is-selected" : ""
      }`}
      style={{
        left: position.x,
        top: position.y,
        width: size.width,
        height: size.height,
      }}
      data-student-card-id={cardId}
      aria-label={`${label} handwriting card`}
    >
      <div
        className="handwriting-panel-head"
        onPointerDown={(event) => {
          if ((event.target as HTMLElement).closest(".handwriting-topic-input")) return;
          onSelect?.(cardId);
        }}
      >
        <button
          type="button"
          className="handwriting-drag-grip handwriting-panel-drag-handle"
          aria-label={`Move ${label}`}
          title="Move card"
          onPointerDown={onDragHandlePointerDown}
          onPointerMove={onDragHandlePointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onLostPointerCapture={() => {
            dragRef.current = null;
          }}
        >
          <GripVertical size={14} aria-hidden="true" />
        </button>
        <input
          className="handwriting-topic-input"
          value={draftLabel}
          onPointerDown={(event) => event.stopPropagation()}
          onChange={(event) => setDraftLabel(event.currentTarget.value)}
          onBlur={() => onRename(cardId, draftLabel)}
          aria-label="Student card topic"
        />
      </div>
      <div className="handwriting-surface">
        <canvas
          ref={canvasRef}
          width={1200}
          height={900}
          className="handwriting-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        />
      </div>
      <button
        className="handwriting-resize"
        type="button"
        aria-label="Resize handwriting panel"
        onPointerDown={onResizePointerDown}
        onPointerMove={onResizePointerMove}
        onPointerUp={endResize}
        onPointerCancel={endResize}
        onLostPointerCapture={() => {
          resizeRef.current = null;
        }}
      />
    </section>
  );
}

export default memo(HandwritingPanel);

function pointerXY(canvas: HTMLCanvasElement, event: PointerEvent) {
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width / rect.width;
  const sy = canvas.height / rect.height;
  return {
    x: (event.clientX - rect.left) * sx,
    y: (event.clientY - rect.top) * sy,
  };
}

function drawStroke(ctx: CanvasRenderingContext2D, stroke: Stroke) {
  if (stroke.points.length === 0) return;
  const outline = getStroke(stroke.points, {
    size: stroke.tool === "eraser" ? 28 : 4.5,
    thinning: 0.5,
    smoothing: 0.65,
    streamline: 0.55,
  });
  if (outline.length === 0) return;

  ctx.beginPath();
  ctx.moveTo(outline[0][0], outline[0][1]);
  for (let i = 1; i < outline.length; i++) {
    ctx.lineTo(outline[i][0], outline[i][1]);
  }
  ctx.closePath();
  ctx.fillStyle = stroke.tool === "eraser" ? CANVAS_BG : stroke.color;
  ctx.fill();
}

async function canvasToScaledPngBlob(
  canvas: HTMLCanvasElement,
  maxLongEdge: number,
): Promise<Blob | null> {
  const long = Math.max(canvas.width, canvas.height);
  const scale = long > maxLongEdge ? maxLongEdge / long : 1;
  const w = Math.round(canvas.width * scale);
  const h = Math.round(canvas.height * scale);

  const off = document.createElement("canvas");
  off.width = w;
  off.height = h;
  const octx = off.getContext("2d");
  if (!octx) return null;
  octx.drawImage(canvas, 0, 0, w, h);

  return await new Promise((resolve) =>
    off.toBlob((b) => resolve(b), "image/png"),
  );
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      const result = reader.result as string;
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : result);
    };
    reader.readAsDataURL(blob);
  });
}
