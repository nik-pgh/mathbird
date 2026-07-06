import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import BoardItem from "../whiteboard/BoardItem";
import { parseAiBoardItems } from "../../lib/whiteboardItems";
import { summarizeActualItems } from "../../lib/tutorBoardEvalMetrics";

interface Props {
  items: readonly Record<string, unknown>[];
}

/**
 * Renders the "Actual cards" summary as a hoverable trigger that pops a
 * portal-rendered preview of the extractor's output. Each parsed item is
 * rendered with the production {@link BoardItem} renderer, so the preview
 * matches what the student would see on the live AiBoard.
 *
 * Empty / fully-malformed item lists render a plain em-dash with no popover.
 */
export default function ActualCardsHoverCard({ items }: Props) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null);
  const triggerRef = useRef<HTMLSpanElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const hideTimerRef = useRef<number | null>(null);

  const parsedItems = useMemo(() => parseAiBoardItems(items), [items]);
  const summary = useMemo(() => summarizeActualItems(items), [items]);
  const hasPopover = parsedItems.length > 0;

  useEffect(() => {
    return () => {
      if (hideTimerRef.current !== null) {
        window.clearTimeout(hideTimerRef.current);
      }
    };
  }, []);

  function clearHideTimer() {
    if (hideTimerRef.current !== null) {
      window.clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  }

  function scheduleHide() {
    clearHideTimer();
    hideTimerRef.current = window.setTimeout(() => setOpen(false), 120);
  }

  function positionPopover() {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const margin = 8;
    // Place below the trigger; clamp so it stays on-screen. Final layout
    // (max-height + scroll) keeps the popover reachable regardless of length.
    const x = Math.max(
      margin,
      Math.min(rect.left, window.innerWidth - margin),
    );
    const y = rect.bottom + 6;
    setCoords({ x, y });
  }

  useEffect(() => {
    if (!open) return;
    positionPopover();
    const onScroll = () => positionPopover();
    const onResize = () => positionPopover();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!hasPopover) {
    return <code>{summary}</code>;
  }

  return (
    <>
      <span
        ref={triggerRef}
        className="eval-cards-trigger"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onMouseEnter={() => {
          clearHideTimer();
          setOpen(true);
        }}
        onMouseLeave={scheduleHide}
        onFocus={() => setOpen(true)}
        onBlur={scheduleHide}
      >
        <code>{summary}</code>
      </span>
      {open && coords
        ? createPortal(
            <div
              ref={popoverRef}
              className="eval-cards-popover"
              style={{ left: coords.x, top: coords.y }}
              role="dialog"
              onMouseEnter={clearHideTimer}
              onMouseLeave={scheduleHide}
            >
              <div className="eval-cards-popover-heading">
                {parsedItems.length}{" "}
                {parsedItems.length === 1 ? "card" : "cards"} rendered by
                extractor
              </div>
              <div className="eval-cards-popover-list">
                {parsedItems.map((item) => (
                  <div
                    key={`${item.kind}:${item.id}`}
                    className="eval-cards-popover-item"
                  >
                    <BoardItem item={item} />
                  </div>
                ))}
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
