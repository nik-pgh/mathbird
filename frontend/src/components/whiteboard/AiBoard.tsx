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

// Auto-scroll threshold: if the user is within this many px of the bottom
// when a new item arrives, stick to the bottom; otherwise, leave the
// scroll position alone so they can re-read earlier items in peace.
const STICK_THRESHOLD_PX = 40;

export default function AiBoard() {
  const [items, setItems] = useState<Map<string, AiBoardItem>>(
    () => new Map(),
  );

  const onMessage = useCallback((msg: AiBoardUpdate) => {
    if (msg.op === "clear") {
      setItems(new Map());
      return;
    }
    setItems((prev) => {
      const next = new Map(prev);
      for (const item of msg.items) {
        // delete-then-set so an existing id moves to the end (most recent).
        next.delete(item.id);
        next.set(item.id, item);
      }
      return next;
    });
  }, []);

  useBoardChannel<typeof AI_BOARD_TOPIC, AiBoardUpdate>({
    topic: AI_BOARD_TOPIC,
    decode: decodeAiUpdate,
    encode: encodeAiUpdate,
    onMessage,
  });

  const scrollRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    wasAtBottom.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < STICK_THRESHOLD_PX;
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (wasAtBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [items]);

  const list = Array.from(items.values());

  return (
    <div className="board tutor-board">
      <div className="head">
        <span className="label">Tutor board</span>
        <span className="spacer" />
        <span className="count">
          {list.length === 1 ? "1 item" : `${list.length} items`}
        </span>
      </div>
      <div className="surface" ref={scrollRef} onScroll={onScroll}>
        {list.length === 0 ? (
          <div className="empty">The tutor will sketch problems here.</div>
        ) : (
          list.map((item) => <BoardItem key={item.id} item={item} />)
        )}
      </div>
    </div>
  );
}
