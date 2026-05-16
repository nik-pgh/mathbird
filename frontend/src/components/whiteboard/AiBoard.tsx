import { useCallback, useEffect, useRef, useState } from "react";
import BoardItem from "./BoardItem";
import { useBoardChannel } from "./useBoardChannel";
import {
  AI_BOARD_TOPIC,
  type AiBoardItem,
  type AiBoardUpdate,
  decodeAiUpdate,
  encodeAiUpdate,
} from "../../lib/whiteboard";

/**
 * Renders items the AI publishes on the `ai_board` topic.
 *
 * Local state is a Map<id, item> so `upsert` ops can replace items in place
 * without losing position. `clear` resets the map.
 */
export default function AiBoard() {
  const [items, setItems] = useState<Map<string, AiBoardItem>>(() => new Map());

  const onMessage = useCallback((msg: AiBoardUpdate) => {
    if (msg.op === "clear") {
      setItems(new Map());
      return;
    }
    setItems((prev) => {
      const next = new Map(prev);
      for (const item of msg.items) next.set(item.id, item);
      return next;
    });
  }, []);

  // We never publish from here, but subscribing requires the hook to be
  // initialized with `topic`. `send` is intentionally unused on this side.
  useBoardChannel<typeof AI_BOARD_TOPIC, AiBoardUpdate>({
    topic: AI_BOARD_TOPIC,
    decode: decodeAiUpdate,
    encode: encodeAiUpdate,
    onMessage,
  });

  // Auto-scroll to the newest item.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items]);

  return (
    <div className="ai-board" ref={scrollRef}>
      <div className="board-header">Tutor</div>
      {items.size === 0 ? (
        <div className="board-empty">자, 시작해 볼까요? 답을 함께 풀어보아요.</div>
      ) : (
        Array.from(items.values()).map((item) => <BoardItem key={item.id} item={item} />)
      )}
    </div>
  );
}
