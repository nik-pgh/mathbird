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
      for (const item of msg.items) next.set(item.id, item);
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
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
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
      <div className="surface" ref={scrollRef}>
        {list.length === 0 ? (
          <div className="empty">The tutor will sketch problems here.</div>
        ) : (
          list.map((item) => <BoardItem key={item.id} item={item} />)
        )}
      </div>
    </div>
  );
}
