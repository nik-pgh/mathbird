import { useEffect, useRef, type KeyboardEvent, type PointerEvent } from "react";
import { GripVertical } from "lucide-react";
import {
  clampStickyNoteSize,
  gridKeyboardResizeStep,
  type GridMovePreview,
} from "../../lib/boardPlacement";
import GridDropPreview from "./GridDropPreview";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import { useGridItemDrag } from "./useGridItemDrag";
import type { Point, Size, StickyNoteState } from "./workspaceTypes";

interface Props {
  notes: StickyNoteState[];
  selectedNoteId: string | null;
  onSelectNote: (id: string) => void;
  onMoveNote: (id: string, position: Point) => void;
  onResizeNote: (id: string, size: Size) => void;
  onTextChange: (id: string, text: string) => void;
  buildMovePreview: (id: string, size: Size, livePosition: Point) => GridMovePreview;
}

interface ResizeState {
  noteId: string;
  pointerId: number;
  startX: number;
  startY: number;
  startSize: Size;
}

const KEYBOARD_RESIZE_DELTAS: Record<string, { width: number; height: number }> = {
  ArrowRight: { width: 1, height: 0 },
  ArrowLeft: { width: -1, height: 0 },
  ArrowDown: { width: 0, height: 1 },
  ArrowUp: { width: 0, height: -1 },
};

function keyboardResizeStep(event: KeyboardEvent<HTMLButtonElement>): number {
  return gridKeyboardResizeStep(event);
}

export default function StickyNoteLayer({
  notes,
  selectedNoteId,
  onSelectNote,
  onMoveNote,
  onResizeNote,
  onTextChange,
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
    onCommit: onMoveNote,
    buildMovePreview,
  });

  useEffect(() => {
    if (notes.length === 0) {
      cancelDrag();
      resizeRef.current = null;
    }
  }, [cancelDrag, notes.length]);

  const beginResize = (
    event: PointerEvent<HTMLButtonElement>,
    note: StickyNoteState,
  ) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    onSelectNote(note.id);
    resizeRef.current = {
      noteId: note.id,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startSize: note.size,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveResize = (event: PointerEvent<HTMLButtonElement>) => {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    const dx = (event.clientX - resize.startX) / viewport.zoom;
    const dy = (event.clientY - resize.startY) / viewport.zoom;
    const delta = Math.abs(dx) > Math.abs(dy) ? dx : dy;
    onResizeNote(resize.noteId, clampStickyNoteSize({
      width: resize.startSize.width + delta,
      height: resize.startSize.height + delta,
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
    note: StickyNoteState,
  ) => {
    const delta = KEYBOARD_RESIZE_DELTAS[event.key];
    if (!delta) return;

    event.preventDefault();
    event.stopPropagation();
    const step = keyboardResizeStep(event);
    const widthDelta = delta.width * step;
    const heightDelta = delta.height * step;
    const edgeDelta = widthDelta !== 0 ? widthDelta : heightDelta;
    onResizeNote(note.id, clampStickyNoteSize({
      width: note.size.width + edgeDelta,
      height: note.size.height + edgeDelta,
    }));
  };

  return (
    <div className="sticky-note-layer" aria-label="Private sticky notes">
      <GridDropPreview preview={preview} size={previewSize} />
      {notes.map((note) => {
        const position = displayPosition(note.id, note.position);
        return (
          <section
            key={note.id}
            className={`sticky-note${selectedNoteId === note.id ? " is-selected" : ""}`}
            style={{
              left: position.x,
              top: position.y,
              width: note.size.width,
              height: note.size.height,
            }}
            data-sticky-note-id={note.id}
            onPointerDown={(event) => {
              if ((event.target as HTMLElement).closest(".sticky-note-text")) return;
              onSelectNote(note.id);
            }}
          >
            <header
              className="sticky-note-handle"
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                onSelectNote(note.id);
                beginDrag(
                  note.id,
                  event.pointerId,
                  event.clientX,
                  event.clientY,
                  note.position,
                  note.size,
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
              <GripVertical size={14} aria-hidden="true" />
            </header>
            <textarea
              className="sticky-note-text"
              value={note.text}
              onChange={(event) => onTextChange(note.id, event.target.value)}
              onPointerDown={(event) => event.stopPropagation()}
              aria-label="Sticky note text"
              spellCheck={false}
            />
            <button
              className="sticky-note-resize"
              type="button"
              aria-label="Resize sticky note"
              onPointerDown={(event) => beginResize(event, note)}
              onPointerMove={moveResize}
              onPointerUp={endResize}
              onPointerCancel={endResize}
              onLostPointerCapture={endResize}
              onKeyDown={(event) => resizeWithKeyboard(event, note)}
            />
          </section>
        );
      })}
    </div>
  );
}
