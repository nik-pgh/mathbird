import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import DOMPurify from "dompurify";
import { Maximize2, Minimize2 } from "lucide-react";
import { CANVAS_WHEEL_IGNORE_ATTR } from "../../lib/canvasViewport";
import {
  clampToCellSpan,
  COLLAPSED_TUTOR_RIBBON_HEIGHT,
  deriveTutorBoardTitle,
  gridKeyboardResizeStep,
  truncateTutorBoardTitle,
  tutorCardSizeForKind,
  type GridMovePreview,
} from "../../lib/boardPlacement";
import { renderMathTextToHtml } from "../../lib/mathText";
import BoardItem from "../whiteboard/BoardItem";
import GridDropPreview from "./GridDropPreview";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import { useGridItemDrag } from "./useGridItemDrag";
import type { BoardObject, Point, Size } from "./workspaceTypes";

interface Props {
  objects: BoardObject[];
  onMoveObject: (id: string, position: Point) => void;
  onResizeObject: (id: string, size: { width: number; height: number }) => void;
  onActivateObject: (id: string) => void;
  onCollapseObject: (id: string) => void;
  buildMovePreview: (id: string, size: Size, livePosition: Point) => GridMovePreview;
}

interface ResizeState {
  objectId: string;
  pointerId: number;
  startX: number;
  startY: number;
  startSize: { width: number; height: number };
}

const KIND_LABELS: Record<BoardObject["kind"], string> = {
  text: "Text",
  plot: "Graph",
  shape: "Sketch",
  diagram: "Diagram",
};

const KEYBOARD_RESIZE_DELTAS: Record<string, { width: number; height: number }> = {
  ArrowRight: { width: 1, height: 0 },
  ArrowLeft: { width: -1, height: 0 },
  ArrowDown: { width: 0, height: 1 },
  ArrowUp: { width: 0, height: -1 },
};

function keyboardResizeStep(event: KeyboardEvent<HTMLButtonElement>): number {
  return gridKeyboardResizeStep(event);
}

export default function TutorObjectLayer({
  objects,
  onMoveObject,
  onResizeObject,
  onActivateObject,
  onCollapseObject,
  buildMovePreview,
}: Props) {
  const resizeRef = useRef<ResizeState | null>(null);
  const { clientToWorld, viewport } = useCanvasViewportContext();
  const {
    preview,
    previewSize,
    beginDrag,
    moveDrag,
    endDrag,
    cancelDrag,
    displayPosition,
  } = useGridItemDrag({
    clientToWorld,
    onCommit: onMoveObject,
    buildMovePreview,
  });

  const beginResize = (
    event: PointerEvent<HTMLButtonElement>,
    object: BoardObject,
  ) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    resizeRef.current = {
      objectId: object.id,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startSize: object.size ?? tutorCardSizeForKind(object.kind),
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveResize = (event: PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    const dx = (event.clientX - resize.startX) / viewport.zoom;
    const dy = (event.clientY - resize.startY) / viewport.zoom;
    onResizeObject(resize.objectId, clampToCellSpan({
      width: resize.startSize.width + dx,
      height: resize.startSize.height + dy,
    }));
  };

  const endResize = (event: PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    resizeRef.current = null;
  };

  const resizeWithKeyboard = (
    event: KeyboardEvent<HTMLButtonElement>,
    object: BoardObject,
    size: { width: number; height: number },
  ) => {
    const delta = KEYBOARD_RESIZE_DELTAS[event.key];
    if (!delta) return;

    event.preventDefault();
    event.stopPropagation();
    const step = keyboardResizeStep(event);
    onResizeObject(object.id, clampToCellSpan({
      width: size.width + delta.width * step,
      height: size.height + delta.height * step,
    }));
  };

  return (
    <div className="tutor-object-layer" aria-label="Tutor visual objects">
      <GridDropPreview preview={preview} size={previewSize} />
      {objects.map((object, index) => {
        const size = object.size ?? tutorCardSizeForKind(object.kind);
        const position = displayPosition(object.id, object.position);
        const title = deriveTutorBoardTitle(object.item, index + 1);
        const { display: headerTitle, truncated: titleTruncated } =
          truncateTutorBoardTitle(title);
        const titleHtml = titleTruncated
          ? DOMPurify.sanitize(headerTitle)
          : DOMPurify.sanitize(
              renderMathTextToHtml(headerTitle, { lineBreaks: "collapse" }),
              { USE_PROFILES: { html: true, mathMl: true, svg: true } },
            );
        const isCollapsed = object.collapsed === true;
        const dragSize = isCollapsed
          ? { width: size.width, height: COLLAPSED_TUTOR_RIBBON_HEIGHT }
          : size;

        return (
          <article
            key={object.id}
            className={`tutor-object tutor-object-${object.kind} ${
              isCollapsed ? "tutor-object-collapsed" : "tutor-object-expanded"
            }`}
            style={{
              position: "absolute",
              left: position.x,
              top: position.y,
              width: size.width,
              minHeight: isCollapsed ? COLLAPSED_TUTOR_RIBBON_HEIGHT : undefined,
              height: isCollapsed ? COLLAPSED_TUTOR_RIBBON_HEIGHT : size.height,
            }}
            data-board-object-id={object.id}
            data-board-object-kind={object.kind}
          >
            <div
              className="tutor-object-handle"
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                beginDrag(
                  object.id,
                  event.pointerId,
                  event.clientX,
                  event.clientY,
                  object.position,
                  dragSize,
                );
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                moveDrag(event.pointerId, event.clientX, event.clientY);
              }}
              onPointerUp={(event) => {
                endDrag(event.pointerId);
                if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
              }}
              onPointerCancel={(event) => {
                cancelDrag(event.pointerId);
                if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
              }}
              onLostPointerCapture={() => {
                cancelDrag();
              }}
            >
              <span className="tutor-object-title" title={title}>
                <span
                  className="tutor-object-title-html"
                  dangerouslySetInnerHTML={{ __html: titleHtml }}
                />
              </span>
              <span className="tutor-object-title-actions">
                <span className="tutor-object-kind-pill">
                  {KIND_LABELS[object.kind]}
                </span>
                <button
                  className="tutor-object-title-action"
                  type="button"
                  aria-label={isCollapsed ? "Enlarge tutor board" : "Minimize tutor board"}
                  title={isCollapsed ? "Enlarge" : "Minimize"}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation();
                    if (isCollapsed) {
                      onActivateObject(object.id);
                    } else {
                      onCollapseObject(object.id);
                    }
                  }}
                >
                  {isCollapsed ? (
                    <Maximize2 size={12} aria-hidden="true" />
                  ) : (
                    <Minimize2 size={12} aria-hidden="true" />
                  )}
                </button>
              </span>
            </div>
            {!isCollapsed ? (
              <>
                <div
                  className="tutor-object-body"
                  {...{ [CANVAS_WHEEL_IGNORE_ATTR]: "" }}
                >
                  <BoardItem item={object.item} />
                </div>
                <button
                  className="tutor-object-resize"
                  type="button"
                  aria-label="Resize tutor board"
                  onPointerDown={(event) => beginResize(event, object)}
                  onPointerMove={moveResize}
                  onPointerUp={endResize}
                  onPointerCancel={endResize}
                  onLostPointerCapture={endResize}
                  onKeyDown={(event) => resizeWithKeyboard(event, object, size)}
                />
              </>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
