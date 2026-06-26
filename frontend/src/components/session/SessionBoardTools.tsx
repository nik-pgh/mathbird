import { FileText, FileX, SquarePen, StickyNote as StickyNoteIcon } from "lucide-react";
import { CANVAS_WHEEL_IGNORE_ATTR } from "../../lib/canvasViewport";
import type { TextbookDisplayMode } from "../../lib/pdfWorkspaceLayout";
import BoardInkToolbar from "./BoardInkToolbar";
import type { InkColor, InkTool } from "./workspaceTypes";

interface Props {
  activeDocId: string | null;
  textbookMode: TextbookDisplayMode;
  textbookToggleLabel: string;
  onAddStudentCard: () => void;
  onAddStickyNote: () => void;
  onTextbookToggle: () => void;
  inkTool: InkTool;
  inkColor: InkColor;
  canUndoInk: boolean;
  canClearInk: boolean;
  onInkToolChange: (tool: InkTool) => void;
  onInkColorChange: (color: InkColor) => void;
  onInkUndo: () => void;
  onInkClear: () => void;
}

export default function SessionBoardTools({
  activeDocId,
  textbookMode,
  textbookToggleLabel,
  onAddStudentCard,
  onAddStickyNote,
  onTextbookToggle,
  inkTool,
  inkColor,
  canUndoInk,
  canClearInk,
  onInkToolChange,
  onInkColorChange,
  onInkUndo,
  onInkClear,
}: Props) {
  return (
    <div
      {...{ [CANVAS_WHEEL_IGNORE_ATTR]: "" }}
      className="topbar-board-tools"
      role="toolbar"
      aria-label="Board tools"
    >
      <div className="topbar-board-tools-group">
        <button
          type="button"
          className="topbar-board-tools-button"
          onClick={onAddStudentCard}
          aria-label="Add student card"
          title="Add student card"
        >
          <SquarePen size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="topbar-board-tools-button"
          onClick={onAddStickyNote}
          aria-label="Add sticky note"
          title="Add sticky note"
        >
          <StickyNoteIcon size={16} aria-hidden="true" />
        </button>
        {activeDocId && (
          <button
            type="button"
            className={`topbar-board-tools-button${
              textbookMode !== "collapsed" ? " is-active" : ""
            }`}
            onClick={onTextbookToggle}
            aria-label={textbookToggleLabel}
            title={textbookToggleLabel}
            aria-pressed={textbookMode !== "collapsed"}
          >
            {textbookMode === "collapsed" ? (
              <FileText size={16} aria-hidden="true" />
            ) : (
              <FileX size={16} aria-hidden="true" />
            )}
          </button>
        )}
      </div>

      <BoardInkToolbar
        tool={inkTool}
        color={inkColor}
        canUndo={canUndoInk}
        canClear={canClearInk}
        onToolChange={onInkToolChange}
        onColorChange={onInkColorChange}
        onUndo={onInkUndo}
        onClear={onInkClear}
      />
    </div>
  );
}
