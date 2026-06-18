import { useRef } from "react";
import BoardItem from "../whiteboard/BoardItem";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import type { BoardObject, Point } from "./workspaceTypes";

interface Props {
  objects: BoardObject[];
  onMoveObject: (id: string, position: Point) => void;
  onActivateObject: (id: string) => void;
}

interface DragState {
  objectId: string;
  pointerId: number;
  offset: Point;
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
  onActivateObject,
}: Props) {
  const dragRef = useRef<DragState | null>(null);
  const { clientToWorld } = useCanvasViewportContext();
  const activeObject = objects.find((object) => !object.collapsed) ?? objects.at(-1);
  const collapsedObjects = objects.filter((object) => object.id !== activeObject?.id);

  return (
    <div className="tutor-object-layer" aria-label="Tutor visual objects">
      {activeObject ? (
        <div
          className="tutor-focus-rail"
          style={{
            left: activeObject.position.x,
            top: activeObject.position.y,
            width: activeObject.size?.width,
          }}
        >
          {collapsedObjects.length > 0 ? (
            <div className="tutor-object-history" aria-label="Collapsed tutor cards">
              {collapsedObjects.map((object) => (
                <button
                  key={object.id}
                  type="button"
                  className={`tutor-object-collapsed tutor-object-collapsed-${object.kind}`}
                  onClick={() => onActivateObject(object.id)}
                  title={`Show ${KIND_LABELS[object.kind].toLowerCase()} card`}
                >
                  <span>{KIND_LABELS[object.kind]}</span>
                </button>
              ))}
            </div>
          ) : null}
          <article
            className={`tutor-object tutor-object-expanded tutor-object-${activeObject.kind}`}
            style={{
              width: activeObject.size?.width,
            }}
            data-board-object-id={activeObject.id}
            data-board-object-kind={activeObject.kind}
          >
            <div
              className="tutor-object-handle"
              aria-label={`Move tutor ${KIND_LABELS[activeObject.kind].toLowerCase()} card`}
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                const world = clientToWorld(event.clientX, event.clientY);
                dragRef.current = {
                  objectId: activeObject.id,
                  pointerId: event.pointerId,
                  offset: {
                    x: world.x - activeObject.position.x,
                    y: world.y - activeObject.position.y,
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
              onLostPointerCapture={(event) => {
                const drag = dragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                dragRef.current = null;
              }}
            >
              <span className="tutor-object-title">Tutor Card</span>
              <span className="tutor-object-kind-pill">
                {KIND_LABELS[activeObject.kind]}
              </span>
            </div>
            <div className="tutor-object-body">
              <BoardItem item={activeObject.item} />
            </div>
          </article>
        </div>
      ) : null}
    </div>
  );
}
