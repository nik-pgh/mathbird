import { useCallback, useLayoutEffect, useReducer, useRef, useState } from "react";
import { SquarePen, StickyNote as StickyNoteIcon } from "lucide-react";
import { zoomAtPoint } from "../../lib/canvasViewport";
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
import BoardInkToolbar from "./BoardInkToolbar";
import CanvasViewport from "./CanvasViewport";
import HandwritingPanel from "./HandwritingPanel";
import PrivateBoardInkLayer from "./PrivateBoardInkLayer";
import StickyNoteLayer from "./StickyNoteLayer";
import TextbookOverlay from "./TextbookOverlay";
import TranscriptOverlay from "./TranscriptOverlay";
import TutorObjectLayer from "./TutorObjectLayer";
import VoiceComposer from "./VoiceComposer";
import {
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

interface Props {
  status: "connecting" | "connected" | "disconnected";
  activeDocId: string | null;
  filename: string | null;
  onEnd: () => void;
}

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
  const [workspaceWidth, setWorkspaceWidth] = useState(() =>
    typeof window === "undefined" ? 0 : window.innerWidth,
  );
  const workspaceRef = useRef<HTMLElement>(null);
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

  const resizeStickyNote = useCallback((id: string, size: { width: number; height: number }) => {
    dispatch({ type: "resize_sticky_note", id, size });
  }, []);

  const updateStickyNoteText = useCallback((id: string, text: string) => {
    dispatch({ type: "update_sticky_note_text", id, text });
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
    workspaceWidth,
  });
  const dockWidth = pdfDockWidth(workspaceWidth);

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
    const workspace = workspaceRef.current;
    if (!workspace) return;

    const updateWorkspaceWidth = () => {
      setWorkspaceWidth(workspace.getBoundingClientRect().width);
    };

    updateWorkspaceWidth();
    const observer = new ResizeObserver(updateWorkspaceWidth);
    observer.observe(workspace);
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

  return (
    <section
      ref={workspaceRef}
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
      <div className="shared-workspace-main">
        {textbookMode === "docked" && (
          <TextbookOverlay
            docId={activeDocId}
            title={filename}
            displayMode={textbookMode}
            onToggle={() =>
              dispatch({
                type: "set_textbook",
                value: "small",
              })
            }
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
          <div className="board-top-actions">
            <button
              type="button"
              onClick={addStudentCard}
              aria-label="Add student card"
              title="Add student card"
            >
              <SquarePen size={17} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={addStickyNote}
              aria-label="Add sticky note"
              title="Add sticky note"
            >
              <StickyNoteIcon size={17} aria-hidden="true" />
            </button>
            {textbookMode === "collapsed" && (
              <TextbookOverlay
                docId={activeDocId}
                title={filename}
                displayMode={textbookMode}
                onToggle={() =>
                  dispatch({
                    type: "set_textbook",
                    value: "large",
                  })
                }
              />
            )}
          </div>
          {textbookMode === "overlay" && (
            <TextbookOverlay
              docId={activeDocId}
              title={filename}
              displayMode={textbookMode}
              onToggle={() =>
                dispatch({
                  type: "set_textbook",
                  value: "small",
                })
              }
            />
          )}
          <TranscriptOverlay
            open={state.overlays.transcriptOpen}
            onToggle={() => dispatch({ type: "toggle_transcript" })}
          />
          <BoardInkToolbar
            tool={state.ink.tool}
            color={state.ink.color}
            canUndo={canChangeActiveInk}
            canClear={canChangeActiveInk}
            onToolChange={setInkTool}
            onColorChange={setInkColor}
            onUndo={undoActiveInk}
            onClear={clearActiveInk}
          />
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
            />
            <StickyNoteLayer
              notes={state.stickyNotes}
              onMoveNote={moveStickyNote}
              onResizeNote={resizeStickyNote}
              onTextChange={updateStickyNoteText}
            />
            {state.studentCards.map((card) => (
              <HandwritingPanel
                key={card.id}
                cardId={card.id}
                label={card.label}
                position={card.position}
                size={card.size}
                isCapturing={card.isCapturing}
                inkTool={state.ink.tool}
                inkColor={state.ink.color}
                inkCommand={inkCommand}
                onMove={moveStudentCard}
                onResize={resizeStudentCard}
                onRename={renameStudentCard}
                onCaptureStateChange={setStudentCardCaptureActive}
                onStrokeTargeted={setActiveInkTarget}
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

  const margin = boardWidth <= 560 ? 12 : 18;
  const maxWidth = Math.min(520, boardWidth - margin * 2);
  const width = Math.max(280, maxWidth);
  let height = width * 0.75;

  if (height > boardHeight - margin * 2) {
    height = Math.max(210, boardHeight - margin * 2);
  }

  const finalWidth = Math.min(width, height / 0.75);
  const finalHeight = finalWidth * 0.75;

  return {
    position: {
      x: Math.round((boardWidth - finalWidth) / 2),
      y: Math.round((boardHeight - finalHeight) / 2),
    },
    size: { width: finalWidth, height: finalHeight },
  };
}
