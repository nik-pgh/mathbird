import { useRef } from "react";
import BoardItem from "../whiteboard/BoardItem";
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

export default function TutorObjectLayer({
  objects,
  onMoveObject,
}: Props) {
  const dragRef = useDragRef();

  return (
    <div
      className="tutor-object-layer"
      style={{ position: "relative" }}
      aria-label="Tutor visual objects"
    >
      {objects.map((object) => (
        <article
          key={object.id}
          className={`tutor-object tutor-object-${object.kind}`}
          style={{
            position: "absolute",
            left: object.position.x,
            top: object.position.y,
          }}
          data-board-object-id={object.id}
          data-board-object-kind={object.kind}
        >
          <div
            className="tutor-object-handle"
            aria-label="Move tutor object"
            style={{ touchAction: "none" }}
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              dragRef.current = {
                objectId: object.id,
                pointerId: event.pointerId,
                offset: {
                  x: event.clientX - object.position.x,
                  y: event.clientY - object.position.y,
                },
              };
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              const drag = dragRef.current;
              if (!drag || drag.pointerId !== event.pointerId) return;
              onMoveObject(drag.objectId, {
                x: Math.max(0, event.clientX - drag.offset.x),
                y: Math.max(0, event.clientY - drag.offset.y),
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
            Tutor visual
          </div>
          <BoardItem item={object.item} />
        </article>
      ))}
    </div>
  );
}

function useDragRef() {
  return useRef<DragState | null>(null);
}
