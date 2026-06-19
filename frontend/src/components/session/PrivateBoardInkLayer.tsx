import {
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { getStroke } from "perfect-freehand";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import type {
  InkColor,
  InkTool,
  PrivateBoardInkStroke,
} from "./workspaceTypes";

interface Props {
  strokes: PrivateBoardInkStroke[];
  tool: InkTool;
  color: InkColor;
  onCommitStroke: (stroke: PrivateBoardInkStroke) => void;
}

const WORLD_SIZE = 20000;
const WORLD_ORIGIN = -WORLD_SIZE / 2;

export default function PrivateBoardInkLayer({
  strokes,
  tool,
  color,
  onCommitStroke,
}: Props) {
  const { clientToWorld, isSpacePan } = useCanvasViewportContext();
  const rawMaskId = useId();
  const maskId = `private-board-ink-mask-${rawMaskId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const activePointerRef = useRef<number | null>(null);
  const draftStrokeRef = useRef<PrivateBoardInkStroke | null>(null);
  const [draftStroke, setDraftStroke] = useState<PrivateBoardInkStroke | null>(null);

  const committedPaths = useMemo(
    () =>
      strokes.map((stroke) => ({
        id: stroke.id,
        stroke,
        path: strokeToPath(stroke),
      })),
    [strokes],
  );

  const draftPath = useMemo(
    () => (draftStroke ? strokeToPath(draftStroke) : null),
    [draftStroke],
  );

  const beginStroke = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 || isSpacePan || activePointerRef.current !== null) return;

    blurActiveEditable();
    event.preventDefault();
    event.stopPropagation();
    activePointerRef.current = event.pointerId;
    event.currentTarget.setPointerCapture(event.pointerId);

    const nextStroke: PrivateBoardInkStroke = {
      id: `${Date.now()}-${event.pointerId}`,
      target: { kind: "private_board" },
      tool,
      color,
      points: pointerEventsToPoints([event.nativeEvent], clientToWorld),
    };
    draftStrokeRef.current = nextStroke;
    setDraftStroke(nextStroke);
  };

  const extendStroke = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (activePointerRef.current !== event.pointerId) return;

    event.preventDefault();
    event.stopPropagation();
    const samples = event.nativeEvent.getCoalescedEvents?.() ?? [event.nativeEvent];
    const points = pointerEventsToPoints(samples, clientToWorld);
    const current = draftStrokeRef.current;
    if (!current) return;
    const nextStroke = { ...current, points: [...current.points, ...points] };
    draftStrokeRef.current = nextStroke;
    setDraftStroke(nextStroke);
  };

  const endStroke = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (activePointerRef.current !== event.pointerId) return;

    event.preventDefault();
    event.stopPropagation();
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    const completedStroke = draftStrokeRef.current;
    activePointerRef.current = null;
    draftStrokeRef.current = null;
    setDraftStroke(null);
    if (completedStroke && completedStroke.points.length > 1) {
      onCommitStroke(completedStroke);
    }
  };

  const cancelStroke = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (activePointerRef.current !== event.pointerId) return;

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    activePointerRef.current = null;
    draftStrokeRef.current = null;
    setDraftStroke(null);
  };

  return (
    <div className="private-board-ink-layer" aria-hidden="true">
      <svg
        className="private-board-ink-svg"
        viewBox={`${WORLD_ORIGIN} ${WORLD_ORIGIN} ${WORLD_SIZE} ${WORLD_SIZE}`}
        onPointerDown={beginStroke}
        onPointerMove={extendStroke}
        onPointerUp={endStroke}
        onPointerCancel={cancelStroke}
        onLostPointerCapture={() => {
          activePointerRef.current = null;
          draftStrokeRef.current = null;
          setDraftStroke(null);
        }}
      >
        <defs>
          <mask id={maskId} maskUnits="userSpaceOnUse">
            <rect
              x={WORLD_ORIGIN}
              y={WORLD_ORIGIN}
              width={WORLD_SIZE}
              height={WORLD_SIZE}
              fill="white"
            />
            {committedPaths.map(({ id, stroke, path }) =>
              stroke.tool === "eraser" && path ? (
                <path key={`mask-${id}`} d={path} fill="black" />
              ) : null,
            )}
            {draftStroke?.tool === "eraser" && draftPath ? (
              <path d={draftPath} fill="black" />
            ) : null}
          </mask>
        </defs>
        <g mask={`url(#${maskId})`}>
          {committedPaths.map(({ id, stroke, path }) =>
            stroke.tool === "pen" && path ? (
              <path key={id} d={path} fill={stroke.color} />
            ) : null,
          )}
          {draftStroke?.tool === "pen" && draftPath ? (
            <path d={draftPath} fill={draftStroke.color} />
          ) : null}
        </g>
      </svg>
    </div>
  );
}

function pointerEventsToPoints(
  events: globalThis.PointerEvent[],
  clientToWorld: (clientX: number, clientY: number) => { x: number; y: number },
): PrivateBoardInkStroke["points"] {
  return events.map((event) => {
    const world = clientToWorld(event.clientX, event.clientY);
    return [world.x, world.y, event.pressure > 0 ? event.pressure : 0.5];
  });
}

function blurActiveEditable() {
  const activeElement = document.activeElement;
  if (!(activeElement instanceof HTMLElement)) return;

  const tagName = activeElement.tagName;
  if (
    tagName === "INPUT" ||
    tagName === "TEXTAREA" ||
    tagName === "SELECT" ||
    activeElement.isContentEditable
  ) {
    activeElement.blur();
  }
}

function strokeToPath(stroke: PrivateBoardInkStroke): string | null {
  if (stroke.points.length === 0) return null;

  const outline = getStroke(stroke.points, {
    size: stroke.tool === "eraser" ? 28 : 5,
    thinning: 0.5,
    smoothing: 0.5,
    streamline: 0.5,
  });
  if (outline.length === 0) return null;

  const [first, ...rest] = outline;
  return [
    `M ${first[0].toFixed(2)} ${first[1].toFixed(2)}`,
    ...rest.map(([x, y]) => `L ${x.toFixed(2)} ${y.toFixed(2)}`),
    "Z",
  ].join(" ");
}
