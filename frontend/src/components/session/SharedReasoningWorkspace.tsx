import { useCallback, useLayoutEffect, useReducer, useRef } from "react";
import {
  AI_BOARD_TOPIC,
  type AiBoardUpdate,
  decodeAiUpdate,
  encodeAiUpdate,
} from "../../lib/whiteboard";
import { useBoardChannel } from "../whiteboard/useBoardChannel";
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

  useLayoutEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const applyResponsiveDefault = () => {
      if (hasCustomizedHandwritingRef.current) return;
      const rect = board.getBoundingClientRect();
      const layout = responsiveHandwritingLayout(rect.width, rect.height);
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
      </div>
      <VoiceComposer status={status} onEnd={onEnd} />
    </section>
  );
}

function responsiveHandwritingLayout(
  boardWidth: number,
  boardHeight: number,
): { position: { x: number; y: number }; size: { width: number; height: number } } | null {
  if (boardWidth > 900 || boardWidth <= 0 || boardHeight <= 0) return null;

  const margin = boardWidth <= 560 ? 12 : 18;
  const textbookHeight = Math.min(boardHeight * 0.3, boardWidth <= 560 ? 240 : 280);
  const top = Math.round(margin + textbookHeight + (boardWidth <= 560 ? 20 : 24));
  const transcriptClearance = 136;
  const maxHeight = Math.max(210, boardHeight - transcriptClearance - top);
  const desiredWidth = Math.min(520, boardWidth - margin * 2);
  const desiredHeight = desiredWidth * 0.75;
  const height = Math.max(210, Math.min(desiredHeight, maxHeight));
  const width = Math.min(desiredWidth, height / 0.75);

  return {
    position: { x: margin, y: top },
    size: { width, height },
  };
}
