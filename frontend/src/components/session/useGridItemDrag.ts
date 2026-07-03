import { useCallback, useRef, useState } from "react";
import {
  type GridMovePreview,
} from "../../lib/boardPlacement";
import type { Point, Size } from "./workspaceTypes";

interface DragRefState {
  id: string;
  pointerId: number;
  offset: Point;
  size: Size;
}

interface UseGridItemDragOptions {
  clientToWorld: (clientX: number, clientY: number) => Point;
  onCommit: (id: string, position: Point) => void;
  buildMovePreview: (
    id: string,
    size: Size,
    livePosition: Point,
  ) => GridMovePreview;
}

export function useGridItemDrag({
  clientToWorld,
  onCommit,
  buildMovePreview,
}: UseGridItemDragOptions) {
  const dragRef = useRef<DragRefState | null>(null);
  const previewRef = useRef<GridMovePreview | null>(null);
  const livePositionRef = useRef<Point | null>(null);
  const [livePosition, setLivePosition] = useState<Point | null>(null);
  const [preview, setPreview] = useState<GridMovePreview | null>(null);
  const [previewSize, setPreviewSize] = useState<Size | null>(null);

  const beginDrag = useCallback(
    (
      id: string,
      pointerId: number,
      clientX: number,
      clientY: number,
      position: Point,
      size: Size,
    ) => {
      const world = clientToWorld(clientX, clientY);
      dragRef.current = {
        id,
        pointerId,
        offset: {
          x: world.x - position.x,
          y: world.y - position.y,
        },
        size,
      };
      livePositionRef.current = position;
      const nextPreview = buildMovePreview(id, size, position);
      previewRef.current = nextPreview;
      setLivePosition(position);
      setPreviewSize(size);
      setPreview(nextPreview);
    },
    [buildMovePreview, clientToWorld],
  );

  const moveDrag = useCallback(
    (pointerId: number, clientX: number, clientY: number) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== pointerId) return;

      const world = clientToWorld(clientX, clientY);
      const nextLive = {
        x: world.x - drag.offset.x,
        y: world.y - drag.offset.y,
      };
      livePositionRef.current = nextLive;
      const nextPreview = buildMovePreview(drag.id, drag.size, nextLive);
      previewRef.current = nextPreview;
      setLivePosition(nextLive);
      setPreview(nextPreview);
    },
    [buildMovePreview, clientToWorld],
  );

  const endDrag = useCallback(
    (pointerId: number) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== pointerId) return;

      const live = livePositionRef.current;
      const latestPreview = live
        ? buildMovePreview(drag.id, drag.size, live)
        : previewRef.current;
      if (latestPreview?.canPlace) {
        onCommit(drag.id, latestPreview.landing);
      }
      dragRef.current = null;
      livePositionRef.current = null;
      previewRef.current = null;
      setLivePosition(null);
      setPreview(null);
      setPreviewSize(null);
    },
    [buildMovePreview, onCommit],
  );

  const cancelDrag = useCallback((pointerId?: number) => {
    const drag = dragRef.current;
    if (!drag) return;
    if (pointerId !== undefined && drag.pointerId !== pointerId) return;
    dragRef.current = null;
    livePositionRef.current = null;
    previewRef.current = null;
    setLivePosition(null);
    setPreview(null);
    setPreviewSize(null);
  }, []);

  const displayPosition = useCallback(
    (id: string, position: Point) => {
      if (dragRef.current?.id === id && livePosition) return livePosition;
      return position;
    },
    [livePosition],
  );

  return {
    preview,
    previewSize,
    beginDrag,
    moveDrag,
    endDrag,
    cancelDrag,
    displayPosition,
  };
}
