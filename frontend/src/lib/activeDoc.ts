/**
 * Active-PDF selection persisted to localStorage.
 *
 * The Library page writes the selected doc_id here; the Session page reads it
 * to pass into ``requestToken`` and to render the in-session PDF popover.
 *
 * Keys:
 * - ``mathbird:active_doc_id``  — string, the selected doc_id
 * - ``mathbird:pdf_popover_geom`` — JSON, popover position/size (managed by
 *    ``PdfPopover``, not this module)
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
