import { useCallback, useLayoutEffect, useReducer, useRef } from "react";
import { zoomAtPoint } from "../../lib/canvasViewport";
import {
  AI_BOARD_TOPIC,
  type AiBoardUpdate,
  decodeAiUpdate,
  encodeAiUpdate,
} from "../../lib/whiteboard";
import { useBoardChannel } from "../whiteboard/useBoardChannel";
import CanvasViewport from "./CanvasViewport";
import HandwritingPanel from "./HandwritingPanel";
import TextbookOverlay from "./TextbookOverlay";
import TranscriptOverlay from "./TranscriptOverlay";
import TutorObjectLayer from "./TutorObjectLayer";
import VoiceComposer from "./VoiceComposer";
import {
  initialWorkspaceState,
  workspaceReducer,
} from "./workspaceReducer";

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
  const boardRef = useRef<HTMLDivElement>(null);
  const hasCustomizedHandwritingRef = useRef(false);

  const onAiMessage = useCallback((msg: AiBoardUpdate) => {
    if (msg.op === "clear") {
      dispatch({ type: "ai_clear" });
      return;
    }
    dispatch({ type: "ai_upsert", items: msg.items });
  }, []);

  useBoardChannel<typeof AI_BOARD_TOPIC, AiBoardUpdate>({
    topic: AI_BOARD_TOPIC,
    decode: decodeAiUpdate,
    encode: encodeAiUpdate,
    onMessage: onAiMessage,
  });

  const moveObject = useCallback((id: string, position: { x: number; y: number }) => {
    dispatch({ type: "move_object", id, position });
  }, []);

  const moveHandwriting = useCallback((position: { x: number; y: number }) => {
    hasCustomizedHandwritingRef.current = true;
    dispatch({ type: "move_handwriting", position });
  }, []);

  const resizeHandwriting = useCallback((size: { width: number; height: number }) => {
    hasCustomizedHandwritingRef.current = true;
    dispatch({ type: "resize_handwriting", size });
  }, []);

  const setCaptureActive = useCallback((value: boolean) => {
    dispatch({ type: "set_capturing", value });
  }, []);

  const setViewport = useCallback((viewport: typeof state.viewport) => {
    dispatch({ type: "set_viewport", viewport });
  }, []);

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
    const board = boardRef.current;
    if (!board) return;

    const applyResponsiveDefault = () => {
      if (hasCustomizedHandwritingRef.current) return;
      const rect = board.getBoundingClientRect();
      const layout = defaultHandwritingLayout(rect.width, rect.height);
      if (!layout) return;
      dispatch({ type: "move_handwriting", position: layout.position });
      dispatch({ type: "resize_handwriting", size: layout.size });
    };

    applyResponsiveDefault();
    const observer = new ResizeObserver(applyResponsiveDefault);
    observer.observe(board);
    return () => observer.disconnect();
  }, []);

  return (
    <section className="shared-workspace">
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
        <TextbookOverlay
          docId={activeDocId}
          title={filename}
          mode={state.overlays.textbook}
          onToggle={() =>
            dispatch({
              type: "set_textbook",
              value: state.overlays.textbook === "large" ? "small" : "large",
            })
          }
        />
        <TranscriptOverlay
          open={state.overlays.transcriptOpen}
          onToggle={() => dispatch({ type: "toggle_transcript" })}
        />
        <CanvasViewport
          boardRef={boardRef}
          viewport={state.viewport}
          onViewportChange={setViewport}
        >
          <TutorObjectLayer objects={state.objects} onMoveObject={moveObject} />
          <HandwritingPanel
            position={state.handwriting.position}
            size={state.handwriting.size}
            isCapturing={state.handwriting.isCapturing}
            onMove={moveHandwriting}
            onResize={resizeHandwriting}
            onCaptureStateChange={setCaptureActive}
          />
        </CanvasViewport>
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
