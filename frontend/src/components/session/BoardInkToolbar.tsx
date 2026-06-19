import type { CSSProperties } from "react";
import { Eraser, Pencil, Trash2, Undo2 } from "lucide-react";
import type { InkColor, InkTool } from "./workspaceTypes";

interface BoardInkToolbarProps {
  tool: InkTool;
  color: InkColor;
  canUndo: boolean;
  canClear: boolean;
  onToolChange: (tool: InkTool) => void;
  onColorChange: (color: InkColor) => void;
  onUndo: () => void;
  onClear: () => void;
}

const INK_COLORS: InkColor[] = ["#2b6258", "#ff775f", "#2f6fed", "#7c4dff"];
const ICON_SIZE = 16;

export default function BoardInkToolbar({
  tool,
  color,
  canUndo,
  canClear,
  onToolChange,
  onColorChange,
  onUndo,
  onClear,
}: BoardInkToolbarProps) {
  return (
    <div
      className="board-ink-toolbar"
      role="toolbar"
      aria-label="Board ink tools"
      onPointerDown={(event) => event.stopPropagation()}
      onPointerUp={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        className={tool === "pen" ? "active" : ""}
        onClick={() => onToolChange("pen")}
        aria-label="Pen"
        title="Pen"
        aria-pressed={tool === "pen"}
      >
        <Pencil size={ICON_SIZE} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={tool === "eraser" ? "active" : ""}
        onClick={() => onToolChange("eraser")}
        aria-label="Eraser"
        title="Eraser"
        aria-pressed={tool === "eraser"}
      >
        <Eraser size={ICON_SIZE} aria-hidden="true" />
      </button>
      <span className="board-ink-divider" aria-hidden="true" />
      {INK_COLORS.map((inkColor) => (
        <button
          key={inkColor}
          type="button"
          className={color === inkColor ? "ink-color-swatch active" : "ink-color-swatch"}
          style={{ "--ink-color": inkColor } as CSSProperties}
          onClick={() => onColorChange(inkColor)}
          aria-label={`Ink color ${inkColor}`}
          title={`Ink color ${inkColor}`}
          aria-pressed={color === inkColor}
        />
      ))}
      <span className="board-ink-divider" aria-hidden="true" />
      <button
        type="button"
        onClick={onUndo}
        disabled={!canUndo}
        aria-label="Undo ink"
        title="Undo ink"
      >
        <Undo2 size={ICON_SIZE} aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onClear}
        disabled={!canClear}
        aria-label="Clear ink"
        title="Clear ink"
      >
        <Trash2 size={ICON_SIZE} aria-hidden="true" />
      </button>
    </div>
  );
}
