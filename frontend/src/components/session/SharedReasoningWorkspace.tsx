import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from "react";
import { isDeleteShortcutKey, isEditableTarget, zoomAtPoint } from "../../lib/canvasViewport";
import {
  pdfDockWidth,
  textbookDisplayMode,
} from "../../lib/pdfWorkspaceLayout";
import {
  AI_BOARD_TOPIC,
  type AiBoardUpdate,
  decodeAiUpdate,
  encodeAiUpdate,
} from "../../lib/whiteboard";
import { useBoardChannel } from "../whiteboard/useBoardChannel";
import {
  clampStudentCardSize,
  GRID_CELL_SIZE,
  snapPositionToGrid,
  studentCardDefaultSize,
} from "../../lib/boardPlacement";
import CanvasViewport from "./CanvasViewport";
import HandwritingPanel from "./HandwritingPanel";
import PrivateBoardInkLayer from "./PrivateBoardInkLayer";
import StickyNoteLayer from "./StickyNoteLayer";
import TextbookOverlay from "./TextbookOverlay";
import TranscriptOverlay from "./TranscriptOverlay";
import TutorObjectLayer from "./TutorObjectLayer";
import SessionProgressBridge from "../progress/SessionProgressBridge";
import SessionBoardTools from "./SessionBoardTools";
import { useRegisterSessionToolbar } from "./SessionToolbarContext";
import VoiceComposer from "./VoiceComposer";
import {
  buildGridMovePreview,
  initialWorkspaceState,
  workspaceReducer,
} from "./workspaceReducer";
import type {
  InkColor,
  InkTarget,
  InkTool,
  PrivateBoardInkStroke,
} from "./workspaceTypes";

type InkCommand = {
  id: number;
  target: Extract<InkTarget, { kind: "student_card" }>;
  action: "undo" | "clear";
} | null;

type WorkspaceSize = {
  width: number;
  height: number;
};

interface Props {
  status: "connecting" | "connected" | "disconnected";
  activeDocId: string | null;
  filename: string | null;
  onEnd: () => void;
}

type WorkspaceSelection =
  | { kind: "student_card"; id: string }
  | { kind: "sticky_note"; id: string };

export default function SharedReasoningWorkspace({
  status,
  activeDocId,
  filename,
  onEnd,
}: Props) {
  const [state, dispatch] = useReducer(
    workspaceReducer,
    initialWorkspaceState,
  );
  const [inkCommand, setInkCommand] = useState<InkCommand>(null);
  const [selection, setSelection] = useState<WorkspaceSelection | null>(null);
  const selectionRef = useRef<WorkspaceSelection | null>(null);
  selectionRef.current = selection;
  const [workspaceSize, setWorkspaceSize] = useState<WorkspaceSize>(() => ({
    width: typeof window === "undefined" ? 0 : window.innerWidth,
    height: typeof window === "undefined" ? 0 : window.innerHeight,
  }));
  const workspaceMainRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const hasCustomizedHandwritingRef = useRef(false);
  const inkCommandIdRef = useRef(0);

  const getBoardSize = useCallback(() => {
    const rect = boardRef.current?.getBoundingClientRect();
    return {
      width: rect?.width ?? 900,
      height: rect?.height ?? 640,
    };
  }, []);

  const onAiMessage = useCallback((msg: AiBoardUpdate) => {
    if (msg.op === "clear") {
      dispatch({ type: "ai_clear" });
      return;
    }
    dispatch({ type: "ai_upsert", items: msg.items, boardSize: getBoardSize() });
  }, [getBoardSize]);

  useBoardChannel<typeof AI_BOARD_TOPIC, AiBoardUpdate>({
    topic: AI_BOARD_TOPIC,
    decode: decodeAiUpdate,
    encode: encodeAiUpdate,
    onMessage: onAiMessage,
  });

  const moveObject = useCallback((id: string, position: { x: number; y: number }) => {
    dispatch({ type: "move_object", id, position });
  }, []);

  const resizeObject = useCallback(
    (id: string, size: { width: number; height: number }) => {
      dispatch({ type: "resize_object", id, size, boardSize: getBoardSize() });
    },
    [getBoardSize],
  );

  const activateObject = useCallback((id: string) => {
    dispatch({ type: "activate_object", id, boardSize: getBoardSize() });
  }, [getBoardSize]);

  const collapseObject = useCallback((id: string) => {
    dispatch({ type: "collapse_object", id, boardSize: getBoardSize() });
  }, [getBoardSize]);

  const setViewport = useCallback((viewport: typeof state.viewport) => {
    dispatch({ type: "set_viewport", viewport });
  }, []);

  const addStudentCard = useCallback(() => {
    const rect = boardRef.current?.getBoundingClientRect();
    dispatch({
      type: "add_student_card",
      boardSize: {
        width: rect?.width ?? 900,
        height: rect?.height ?? 600,
      },
    });
  }, []);

  const addStickyNote = useCallback(() => {
    dispatch({
      type: "add_sticky_note",
      boardSize: getBoardSize(),
    });
  }, [getBoardSize]);

  const moveStudentCard = useCallback(
    (id: string, position: { x: number; y: number }) => {
      if (id === "student-card-1") {
        hasCustomizedHandwritingRef.current = true;
      }
      dispatch({ type: "move_student_card", id, position });
    },
    [],
  );

  const resizeStudentCard = useCallback(
    (id: string, size: { width: number; height: number }) => {
      if (id === "student-card-1") {
        hasCustomizedHandwritingRef.current = true;
      }
      dispatch({ type: "resize_student_card", id, size });
    },
    [],
  );

  const renameStudentCard = useCallback((id: string, label: string) => {
    dispatch({ type: "rename_student_card", id, label });
  }, []);

  const setStudentCardCaptureActive = useCallback((id: string, value: boolean) => {
    dispatch({ type: "set_student_card_capturing", id, value });
  }, []);

  const moveStickyNote = useCallback((id: string, position: { x: number; y: number }) => {
    dispatch({ type: "move_sticky_note", id, position });
  }, []);

  const buildMovePreview = useCallback(
    (id: string, size: { width: number; height: number }, livePosition: { x: number; y: number }) =>
      buildGridMovePreview(state, id, size, livePosition),
    [state],
  );

  const resizeStickyNote = useCallback((id: string, size: { width: number; height: number }) => {
    dispatch({ type: "resize_sticky_note", id, size });
  }, []);

  const updateStickyNoteText = useCallback((id: string, text: string) => {
    dispatch({ type: "update_sticky_note_text", id, text });
  }, []);

  const deleteStudentCard = useCallback((id: string) => {
    dispatch({ type: "delete_student_card", id });
  }, []);

  const deleteStickyNote = useCallback((id: string) => {
    dispatch({ type: "delete_sticky_note", id });
  }, []);

  const selectStudentCard = useCallback((id: string) => {
    setSelection({ kind: "student_card", id });
  }, []);

  const selectStickyNote = useCallback((id: string) => {
    setSelection({ kind: "sticky_note", id });
  }, []);

  const clearSelection = useCallback(() => {
    setSelection(null);
  }, []);

  const setInkTool = useCallback((tool: InkTool) => {
    dispatch({ type: "set_ink_tool", tool });
  }, []);

  const setInkColor = useCallback((color: InkColor) => {
    dispatch({ type: "set_ink_color", color });
  }, []);

  const commitPrivateBoardStroke = useCallback((stroke: PrivateBoardInkStroke) => {
    dispatch({ type: "commit_private_board_stroke", stroke });
  }, []);

  const setActiveInkTarget = useCallback((target: InkTarget) => {
    dispatch({ type: "set_active_ink_target", target });
  }, []);

  const undoActiveInk = useCallback(() => {
    const activeTarget = state.ink.activeTarget;
    if (activeTarget.kind === "student_card") {
      inkCommandIdRef.current += 1;
      setInkCommand({
        id: inkCommandIdRef.current,
        target: activeTarget,
        action: "undo",
      });
      return;
    }

    if (activeTarget.kind === "private_board") {
      dispatch({ type: "undo_active_ink" });
    }
  }, [state.ink.activeTarget]);

  const clearActiveInk = useCallback(() => {
    const activeTarget = state.ink.activeTarget;
    if (activeTarget.kind === "student_card") {
      inkCommandIdRef.current += 1;
      setInkCommand({
        id: inkCommandIdRef.current,
        target: activeTarget,
        action: "clear",
      });
      return;
    }

    if (activeTarget.kind === "private_board") {
      dispatch({ type: "clear_active_ink" });
    }
  }, [state.ink.activeTarget]);

  const canChangeActiveInk =
    state.ink.activeTarget.kind === "student_card" ||
    (state.ink.activeTarget.kind === "private_board" &&
      state.privateBoardStrokes.length > 0);
  const textbookMode = textbookDisplayMode({
    hasDocument: Boolean(activeDocId),
    textbook: state.overlays.textbook,
    workspaceWidth: workspaceSize.width,
  });
  const dockWidth = pdfDockWidth(workspaceSize.width, workspaceSize.height);
  const textbookToggleLabel = textbookMode === "collapsed"
    ? `Open textbook${filename ? `: ${filename}` : ""}`
    : `Close textbook${filename ? `: ${filename}` : ""}`;

  const sessionToolbar = useMemo(
    () => (
      <SessionBoardTools
        activeDocId={activeDocId}
        textbookMode={textbookMode}
        textbookToggleLabel={textbookToggleLabel}
        onAddStudentCard={addStudentCard}
        onAddStickyNote={addStickyNote}
        onTextbookToggle={() =>
          dispatch({
            type: "set_textbook",
            value: textbookMode === "collapsed" ? "large" : "small",
          })
        }
        inkTool={state.ink.tool}
        inkColor={state.ink.color}
        canUndoInk={canChangeActiveInk}
        canClearInk={canChangeActiveInk}
        onInkToolChange={setInkTool}
        onInkColorChange={setInkColor}
        onInkUndo={undoActiveInk}
        onInkClear={clearActiveInk}
      />
    ),
    [
      activeDocId,
      addStickyNote,
      addStudentCard,
      canChangeActiveInk,
      clearActiveInk,
      setInkColor,
      setInkTool,
      state.ink.color,
      state.ink.tool,
      textbookMode,
      textbookToggleLabel,
      undoActiveInk,
    ],
  );

  useRegisterSessionToolbar(sessionToolbar);

  const zoomFromCenter = useCallback(
    (factor: number) => {
      const board = boardRef.current;
      if (!board) return;
      const rect = board.getBoundingClientRect();
      dispatch({
        type: "set_viewport",
        viewport: zoomAtPoint(
          state.viewport,
          state.viewport.zoom * factor,
          rect.width / 2,
          rect.height / 2,
        ),
      });
    },
    [state.viewport],
  );

  useLayoutEffect(() => {
    const workspaceMain = workspaceMainRef.current;
    if (!workspaceMain) return;

    const updateWorkspaceSize = () => {
      const rect = workspaceMain.getBoundingClientRect();
      setWorkspaceSize({ width: rect.width, height: rect.height });
    };

    updateWorkspaceSize();
    const observer = new ResizeObserver(updateWorkspaceSize);
    observer.observe(workspaceMain);
    return () => observer.disconnect();
  }, []);

  useLayoutEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const applyResponsiveDefault = () => {
      if (hasCustomizedHandwritingRef.current) return;
      const rect = board.getBoundingClientRect();
      const layout = defaultHandwritingLayout(rect.width, rect.height);
      if (!layout) return;
      dispatch({
        type: "move_student_card",
        id: "student-card-1",
        position: layout.position,
      });
      dispatch({
        type: "resize_student_card",
        id: "student-card-1",
        size: layout.size,
      });
    };

    applyResponsiveDefault();
    const observer = new ResizeObserver(applyResponsiveDefault);
    observer.observe(board);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!selection) return;
    if (
      selection.kind === "student_card"
      && !state.studentCards.some((card) => card.id === selection.id)
    ) {
      setSelection(null);
      return;
    }
    if (
      selection.kind === "sticky_note"
      && !state.stickyNotes.some((note) => note.id === selection.id)
    ) {
      setSelection(null);
    }
  }, [selection, state.studentCards, state.stickyNotes]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const current = selectionRef.current;
      if (!isDeleteShortcutKey(event.key) || !current || isEditableTarget(event.target)) {
        return;
      }
      event.preventDefault();
      if (current.kind === "student_card") {
        deleteStudentCard(current.id);
      } else {
        deleteStickyNote(current.id);
      }
      setSelection(null);
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteStudentCard, deleteStickyNote]);

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest("[data-student-card-id], [data-sticky-note-id]")) return;
      clearSelection();
    };

    board.addEventListener("pointerdown", onPointerDown);
    return () => board.removeEventListener("pointerdown", onPointerDown);
  }, [clearSelection]);

  return (
    <section
      className={
        textbookMode === "docked"
          ? "shared-workspace pdf-docked"
          : "shared-workspace"
      }
      style={
        {
          "--pdf-dock-width": `${dockWidth}px`,
        } as React.CSSProperties
      }
    >
      <div className="shared-workspace-main" ref={workspaceMainRef}>
        {textbookMode === "docked" && (
          <TextbookOverlay
            docId={activeDocId}
            title={filename}
            displayMode={textbookMode}
          />
        )}
        <div
          className="shared-board"
          aria-label="Shared reasoning board"
          ref={boardRef}
          style={
            {
              "--canvas-pan-x": `${state.viewport.pan.x}px`,
              "--canvas-pan-y": `${state.viewport.pan.y}px`,
              "--canvas-zoom": String(state.viewport.zoom),
            } as React.CSSProperties
          }
        >
          {textbookMode === "overlay" && (
            <TextbookOverlay
              docId={activeDocId}
              title={filename}
              displayMode={textbookMode}
              onClose={() => dispatch({ type: "set_textbook", value: "small" })}
            />
          )}
          <TranscriptOverlay
            open={state.overlays.transcriptOpen}
            onToggle={() => dispatch({ type: "toggle_transcript" })}
          />
          <SessionProgressBridge activeDocId={activeDocId} />
          <CanvasViewport
            boardRef={boardRef}
            viewport={state.viewport}
            onViewportChange={setViewport}
          >
            <PrivateBoardInkLayer
              strokes={state.privateBoardStrokes}
              tool={state.ink.tool}
              color={state.ink.color}
              onCommitStroke={commitPrivateBoardStroke}
            />
            <TutorObjectLayer
              objects={state.objects}
              onMoveObject={moveObject}
              onResizeObject={resizeObject}
              onActivateObject={activateObject}
              onCollapseObject={collapseObject}
              buildMovePreview={buildMovePreview}
            />
            <StickyNoteLayer
              notes={state.stickyNotes}
              selectedNoteId={
                selection?.kind === "sticky_note" ? selection.id : null
              }
              onSelectNote={selectStickyNote}
              onMoveNote={moveStickyNote}
              onResizeNote={resizeStickyNote}
              onTextChange={updateStickyNoteText}
              buildMovePreview={buildMovePreview}
            />
            {state.studentCards.map((card) => (
              <HandwritingPanel
                key={card.id}
                cardId={card.id}
                label={card.label}
                position={card.position}
                size={card.size}
                isCapturing={card.isCapturing}
                selected={
                  selection?.kind === "student_card" && selection.id === card.id
                }
                inkTool={state.ink.tool}
                inkColor={state.ink.color}
                inkCommand={inkCommand}
                onMove={moveStudentCard}
                onResize={resizeStudentCard}
                onRename={renameStudentCard}
                onCaptureStateChange={setStudentCardCaptureActive}
                onStrokeTargeted={setActiveInkTarget}
                onSelect={selectStudentCard}
                buildMovePreview={buildMovePreview}
              />
            ))}
          </CanvasViewport>
        </div>
      </div>
      <VoiceComposer
        status={status}
        transcriptOpen={state.overlays.transcriptOpen}
        onTranscriptToggle={() => dispatch({ type: "toggle_transcript" })}
        onEnd={onEnd}
        viewport={state.viewport}
        onZoomIn={() => zoomFromCenter(1.15)}
        onZoomOut={() => zoomFromCenter(1 / 1.15)}
        onResetViewport={() => dispatch({ type: "reset_viewport" })}
      />
    </section>
  );
}

function defaultHandwritingLayout(
  boardWidth: number,
  boardHeight: number,
): { position: { x: number; y: number }; size: { width: number; height: number } } | null {
  if (boardWidth <= 0 || boardHeight <= 0) return null;

  const maxCols = Math.max(2, Math.floor(boardWidth / GRID_CELL_SIZE));
  const width = Math.min(studentCardDefaultSize().width, maxCols * GRID_CELL_SIZE);
  const size = clampStudentCardSize({ width, height: width * 0.75 });

  if (size.height > boardHeight) {
    const fittedWidth = Math.max(270, Math.floor(boardHeight / 0.75 / GRID_CELL_SIZE) * GRID_CELL_SIZE);
    const fitted = clampStudentCardSize({ width: fittedWidth, height: fittedWidth * 0.75 });
    if (fitted.height <= boardHeight && fitted.width <= boardWidth) {
      return {
        position: snapPositionToGrid({
          x: Math.max(0, (boardWidth - fitted.width) / 2),
          y: Math.max(0, (boardHeight - fitted.height) / 2),
        }),
        size: fitted,
      };
    }
  }

  return {
    position: snapPositionToGrid({
      x: Math.max(0, (boardWidth - size.width) / 2),
      y: Math.max(0, (boardHeight - size.height) / 2),
    }),
    size,
  };
}
