import { useEffect, useRef, useState } from "react";

/**
 * Animate `text` character-by-character at `charsPerSecond`.
 *
 * Designed for streaming transcription segments:
 *   - When `text` grows (next STT/TTS chunk), the animation extends to the new tail.
 *   - When `text` is mutated (e.g. STT interim result corrected), it snaps to the
 *     new value instead of trying to "un-type".
 *   - When the component unmounts or `text` resets, the loop stops cleanly.
 */
export function useTypewriter(text: string, charsPerSecond = 45): string {
  const [displayed, setDisplayed] = useState("");
  const targetRef = useRef(text);

  useEffect(() => {
    targetRef.current = text;
  }, [text]);

  useEffect(() => {
    let cancelled = false;
    const intervalMs = 1000 / charsPerSecond;

    function tick() {
      if (cancelled) return;
      setDisplayed((prev) => {
        const target = targetRef.current;
        if (prev === target) return prev;
        if (target.startsWith(prev)) {
          // Streaming case: append the next character.
          return target.slice(0, prev.length + 1);
        }
        // Text was rewritten (STT correction). Snap.
        return target;
      });
      window.setTimeout(tick, intervalMs);
    }
    tick();
    return () => {
      cancelled = true;
    };
  }, [charsPerSecond]);

  return displayed;
}
