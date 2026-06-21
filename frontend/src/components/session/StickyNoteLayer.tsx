import { useEffect, useRef, type KeyboardEvent, type PointerEvent } from "react";
import { GripVertical } from "lucide-react";
import { useCanvasViewportContext } from "./CanvasViewportContext";
import type { Point, Size, StickyNoteState } from "./workspaceTypes";

interface Props {
  notes: StickyNoteState[];
  selectedNoteId: string | null;
  onSelectNote: (id: string) => void;
  onMoveNote: (id: string, position: Point) => void;
  onResizeNote: (id: string, size: Size) => void;
  onTextChange: (id: string, text: string) => void;
}

interface DragState {
  noteId: string;
  pointerId: number;
  offset: Point;
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
  if (event.altKey) return 4;
  if (event.shiftKey) return 48;
  return 16;
}

export default function StickyNoteLayer({
  notes,
  selectedNoteId,
  onSelectNote,
  onMoveNote,
  onResizeNote,
  onTextChange,
}: Props) {
  const dragRef = useRef<DragState | null>(null);
  const resizeRef = useRef<ResizeState | null>(null);
  const { clientToWorld, viewport } = useCanvasViewportContext();

  useEffect(() => {
    if (notes.length === 0) {
      dragRef.current = null;
      resizeRef.current = null;
    }
  }, [notes.length]);

  const beginDrag = (
    event: PointerEvent<HTMLElement>,
    note: StickyNoteState,
  ) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    onSelectNote(note.id);
    const world = clientToWorld(event.clientX, event.clientY);
    dragRef.current = {
      noteId: note.id,
      pointerId: event.pointerId,
      offset: {
        x: world.x - note.position.x,
        y: world.y - note.position.y,
      },
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveDrag = (event: PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const world = clientToWorld(event.clientX, event.clientY);
    onMoveNote(drag.noteId, {
      x: world.x - drag.offset.x,
      y: world.y - drag.offset.y,
    });
  };

  const endDrag = (event: PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
  };

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
    onResizeNote(resize.noteId, {
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

  const resizeWithKeyboard = (
    event: KeyboardEvent<HTMLButtonElement>,
    note: StickyNoteState,
  ) => {
    const delta = KEYBOARD_RESIZE_DELTAS[event.key];
    if (!delta) return;

    event.preventDefault();
    event.stopPropagation();
    const step = keyboardResizeStep(event);
    onResizeNote(note.id, {
      width: note.size.width + delta.width * step,
      height: note.size.height + delta.height * step,
    });
  };

  return (
    <div className="sticky-note-layer" aria-label="Private sticky notes">
      {notes.map((note) => (
        <section
          key={note.id}
          className={`sticky-note${selectedNoteId === note.id ? " is-selected" : ""}`}
          style={{
            left: note.position.x,
            top: note.position.y,
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
            onPointerDown={(event) => beginDrag(event, note)}
            onPointerMove={moveDrag}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onLostPointerCapture={() => {
              dragRef.current = null;
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
      ))}
    </div>
  );
}
