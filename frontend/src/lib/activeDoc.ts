/**
 * Active-PDF selection persisted to localStorage.
 *
 * The Library page writes the selected doc_id here; the Session page reads it
 * to pass into ``requestToken`` and to render the in-session PDF dock.
 *
 * Keys:
 * - ``mathbird:active_doc_id``  — string, the selected doc_id
 */

const KEY = "mathbird:active_doc_id";

export function getActiveDocId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setActiveDocId(docId: string | null): void {
  try {
    if (docId) {
      window.localStorage.setItem(KEY, docId);
    } else {
      window.localStorage.removeItem(KEY);
    }
  } catch {
    /* private-mode browsers — ignore */
  }
}

export function clearActiveDocId(): void {
  setActiveDocId(null);
}

/** Cross-tab updates when another tab changes the active document. */
export function subscribeActiveDocId(
  onChange: (docId: string | null) => void,
): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key !== KEY) return;
    onChange(event.newValue);
  };
  window.addEventListener("storage", onStorage);
  return () => window.removeEventListener("storage", onStorage);
}
