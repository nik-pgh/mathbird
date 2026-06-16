import { useCallback, useReducer } from "react";
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

  return (
    <section className="shared-workspace">
      <div className="shared-board" aria-label="Shared reasoning board">
        <TutorObjectLayer
          objects={state.objects}
          onMoveObject={(id, position) =>
            dispatch({ type: "move_object", id, position })
          }
        />
        <HandwritingPanel
          position={state.handwriting.position}
          size={state.handwriting.size}
          isCapturing={state.handwriting.isCapturing}
          onMove={(position) =>
            dispatch({ type: "move_handwriting", position })
          }
          onResize={(size) => dispatch({ type: "resize_handwriting", size })}
          onCaptureStateChange={(value) =>
            dispatch({ type: "set_capturing", value })
          }
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
