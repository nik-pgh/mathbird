import { useRef } from "react";
import BoardItem from "../whiteboard/BoardItem";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import type { BoardObject, Point } from "./workspaceTypes";

interface Props {
  objects: BoardObject[];
  onMoveObject: (id: string, position: Point) => void;
}

interface DragState {
  objectId: string;
  pointerId: number;
  offset: Point;
}

const KIND_LABELS: Record<BoardObject["kind"], string> = {
  text: "Equation",
  plot: "Graph",
  shape: "Diagram",
  diagram: "Diagram",
};

export default function TutorObjectLayer({
  objects,
  onMoveObject,
}: Props) {
  const dragRef = useRef<DragState | null>(null);
  const { clientToWorld } = useCanvasViewportContext();

  return (
    <div className="tutor-object-layer" aria-label="Tutor visual objects">
      {objects.map((object) => (
        <article
          key={object.id}
          className={`tutor-object tutor-object-${object.kind}`}
          style={{
            left: object.position.x,
            top: object.position.y,
          }}
          data-board-object-id={object.id}
          data-board-object-kind={object.kind}
        >
          <div
            className="tutor-object-handle"
            aria-label={`Move tutor ${KIND_LABELS[object.kind].toLowerCase()} card`}
            onPointerDown={(event) => {
                if (event.button !== 0) return;
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
              onLostPointerCapture={(event) => {
                const drag = dragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                dragRef.current = null;
              }}
            >
              <span className="tutor-object-title">Tutor Card</span>
            <span className="tutor-object-kind-pill">
              {KIND_LABELS[object.kind]}
            </span>
          </div>
          <div className="tutor-object-body">
            <BoardItem item={object.item} />
          </div>
        </article>
      ))}
    </div>
  );
}
