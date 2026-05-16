import { useCallback, useEffect, useRef, useState } from "react";
import { getStroke } from "perfect-freehand";
import { useBoardChannel } from "./useBoardChannel";
import {
  USER_BOARD_TOPIC,
  type UserBoardSnapshot,
  decodeUserSnapshot,
  encodeUserSnapshot,
} from "../../lib/whiteboard";

const SNAPSHOT_INTERVAL_MS = 2000;
const MAX_LONG_EDGE = 512;

type Tool = "pen" | "eraser";
type Point = [number, number, number]; // x, y, pressure
type Stroke = { tool: Tool; points: Point[] };

interface UserBoardProps {
  enabled?: boolean;
}

/**
 * Freehand canvas. Strokes are stored in component state only — no
 * localStorage, no sync with the agent's local copy. The agent only ever sees
 * the rendered PNG.
 *
 * Snapshots are debounced: any stroke event schedules a snapshot
 * SNAPSHOT_INTERVAL_MS in the future; new strokes reset the timer. After
 * "Clear" we publish a single is_empty=true snapshot so the agent learns the
 * board is blank without paying a vision-LLM round-trip.
 */
export default function UserBoard({ enabled = true }: UserBoardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [tool, setTool] = useState<Tool>("pen");
  const [drawing, setDrawing] = useState<Stroke | null>(null);

  const { send } = useBoardChannel<typeof USER_BOARD_TOPIC, UserBoardSnapshot>({
    topic: USER_BOARD_TOPIC,
    decode: decodeUserSnapshot,
    encode: encodeUserSnapshot,
  });

  // ── Redraw whenever strokes change ────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#1a1a1f";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const allStrokes = drawing ? [...strokes, drawing] : strokes;
    for (const stroke of allStrokes) {
      drawStroke(ctx, stroke);
    }
  }, [strokes, drawing]);

  // ── Debounced snapshot loop ───────────────────────────────────────────────
  const snapshotTimerRef = useRef<number | null>(null);
  const scheduleSnapshot = useCallback(() => {
    if (!enabled) return;
    if (snapshotTimerRef.current !== null) {
      window.clearTimeout(snapshotTimerRef.current);
    }
    snapshotTimerRef.current = window.setTimeout(async () => {
      snapshotTimerRef.current = null;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const blob = await canvasToScaledPngBlob(canvas, MAX_LONG_EDGE);
      if (!blob) return;
      const png_b64 = await blobToBase64(blob);
      await send({ png_b64, captured_at_ms: Date.now(), is_empty: false });
    }, SNAPSHOT_INTERVAL_MS);
  }, [send, enabled]);

  useEffect(() => () => {
    if (snapshotTimerRef.current !== null) window.clearTimeout(snapshotTimerRef.current);
  }, []);

  // ── Pointer handlers ──────────────────────────────────────────────────────
  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const pt = pointerXY(e);
    setDrawing({ tool, points: [[pt.x, pt.y, e.pressure || 0.5]] });
    (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing) return;
    const pt = pointerXY(e);
    setDrawing({ ...drawing, points: [...drawing.points, [pt.x, pt.y, e.pressure || 0.5]] });
  };
  const onPointerUp = () => {
    if (!drawing) return;
    setStrokes((prev) => [...prev, drawing]);
    setDrawing(null);
    scheduleSnapshot();
  };

  const undo = () => {
    setStrokes((prev) => prev.slice(0, -1));
    scheduleSnapshot();
  };
  const clear = async () => {
    setStrokes([]);
    if (snapshotTimerRef.current !== null) {
      window.clearTimeout(snapshotTimerRef.current);
      snapshotTimerRef.current = null;
    }
    if (enabled) {
      await send({ png_b64: "", captured_at_ms: Date.now(), is_empty: true });
    }
  };

  return (
    <div className="user-board">
      <div className="board-header">You</div>
      <div className="user-board-toolbar">
        <button
          className={tool === "pen" ? "active" : ""}
          onClick={() => setTool("pen")}
          aria-label="Pen"
        >
          Pen
        </button>
        <button
          className={tool === "eraser" ? "active" : ""}
          onClick={() => setTool("eraser")}
          aria-label="Eraser"
        >
          Eraser
        </button>
        <button onClick={undo} disabled={strokes.length === 0} aria-label="Undo">
          Undo
        </button>
        <button onClick={clear} disabled={strokes.length === 0} aria-label="Clear">
          Clear
        </button>
      </div>
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        className="user-board-canvas"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      />
    </div>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────────

function pointerXY(e: React.PointerEvent<HTMLCanvasElement>) {
  const rect = e.currentTarget.getBoundingClientRect();
  const sx = e.currentTarget.width / rect.width;
  const sy = e.currentTarget.height / rect.height;
  return { x: (e.clientX - rect.left) * sx, y: (e.clientY - rect.top) * sy };
}

function drawStroke(ctx: CanvasRenderingContext2D, stroke: Stroke) {
  if (stroke.points.length === 0) return;
  const outline = getStroke(stroke.points, {
    size: stroke.tool === "eraser" ? 24 : 4,
    thinning: 0.5,
    smoothing: 0.5,
    streamline: 0.5,
  });
  if (outline.length === 0) return;

  ctx.beginPath();
  ctx.moveTo(outline[0][0], outline[0][1]);
  for (let i = 1; i < outline.length; i++) {
    ctx.lineTo(outline[i][0], outline[i][1]);
  }
  ctx.closePath();
  if (stroke.tool === "eraser") {
    ctx.fillStyle = "#1a1a1f";
  } else {
    ctx.fillStyle = "#e8e8ee";
  }
  ctx.fill();
}

async function canvasToScaledPngBlob(
  canvas: HTMLCanvasElement,
  maxLongEdge: number
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

  return await new Promise((resolve) => off.toBlob((b) => resolve(b), "image/png"));
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      const result = reader.result as string;
      // result looks like "data:image/png;base64,AAAA..."
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : result);
    };
    reader.readAsDataURL(blob);
  });
}
