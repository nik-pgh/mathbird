import { useRef, type PointerEvent } from "react";
import {
  COLLAPSED_TUTOR_RIBBON_HEIGHT,
  deriveTutorBoardTitle,
  tutorCardSizeForKind,
} from "../../lib/boardPlacement";
import BoardItem from "../whiteboard/BoardItem";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import type { BoardObject, Point } from "./workspaceTypes";

interface Props {
  objects: BoardObject[];
  onMoveObject: (id: string, position: Point) => void;
  onResizeObject: (id: string, size: { width: number; height: number }) => void;
  onActivateObject: (id: string) => void;
}

interface DragState {
  objectId: string;
  pointerId: number;
  offset: Point;
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

export default function TutorObjectLayer({
  objects,
  onMoveObject,
  onResizeObject,
  onActivateObject,
}: Props) {
  const dragRef = useRef<DragState | null>(null);
  const resizeRef = useRef<ResizeState | null>(null);
  const { clientToWorld, viewport } = useCanvasViewportContext();

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
    onResizeObject(resize.objectId, {
      width: resize.startSize.width + dx,
      height: resize.startSize.height + dy,
    });
  };

  const endResize = (event: PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    resizeRef.current = null;
  };

  return (
    <div className="tutor-object-layer" aria-label="Tutor visual objects">
      {objects.map((object, index) => {
        const size = object.size ?? tutorCardSizeForKind(object.kind);
        const title = deriveTutorBoardTitle(object.item, index + 1);
        const isCollapsed = object.collapsed === true;

        return (
          <article
            key={object.id}
            className={`tutor-object tutor-object-${object.kind} ${
              isCollapsed ? "tutor-object-collapsed" : "tutor-object-expanded"
            }`}
            style={{
              position: "absolute",
              left: object.position.x,
              top: object.position.y,
              width: size.width,
              minHeight: isCollapsed ? COLLAPSED_TUTOR_RIBBON_HEIGHT : undefined,
              height: isCollapsed ? COLLAPSED_TUTOR_RIBBON_HEIGHT : size.height,
            }}
            data-board-object-id={object.id}
            data-board-object-kind={object.kind}
          >
            <div
              className="tutor-object-handle"
              role={isCollapsed ? "button" : undefined}
              tabIndex={isCollapsed ? 0 : undefined}
              aria-label={`${isCollapsed ? "Expand" : "Move"} tutor ${KIND_LABELS[object.kind].toLowerCase()} card`}
              onClick={() => {
                if (isCollapsed) onActivateObject(object.id);
              }}
              onKeyDown={(event) => {
                if (!isCollapsed) return;
                if (event.key === " ") {
                  event.preventDefault();
                  onActivateObject(object.id);
                  return;
                }
                if (event.key === "Enter") {
                  onActivateObject(object.id);
                }
              }}
              onPointerDown={(event) => {
                if (isCollapsed || event.button !== 0) return;
                const world = clientToWorld(event.clientX, event.clientY);
                dragRef.current = {
                  objectId: object.id,
                  pointerId: event.pointerId,
                  offset: {
                    x: world.x - object.position.x,
                    y: world.y - object.position.y,
                  },
                };
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                const drag = dragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                const world = clientToWorld(event.clientX, event.clientY);
                onMoveObject(drag.objectId, {
                  x: world.x - drag.offset.x,
                  y: world.y - drag.offset.y,
                });
              }}
              onPointerUp={(event) => {
                const drag = dragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
                dragRef.current = null;
              }}
              onPointerCancel={(event) => {
                const drag = dragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
                dragRef.current = null;
              }}
              onLostPointerCapture={() => {
                dragRef.current = null;
              }}
            >
              <span className="tutor-object-title">{title}</span>
              <span className="tutor-object-kind-pill">
                {KIND_LABELS[object.kind]}
              </span>
            </div>
            {!isCollapsed ? (
              <>
                <div className="tutor-object-body">
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
                />
              </>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
