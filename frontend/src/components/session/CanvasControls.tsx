import { formatZoomPercent } from "../../lib/canvasViewport";
import type { ViewportState } from "./workspaceTypes";

interface Props {
  viewport: ViewportState;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}

export default function CanvasControls({
  viewport,
  onZoomIn,
  onZoomOut,
  onReset,
}: Props) {
  return (
    <div className="canvas-controls" aria-label="Canvas zoom controls">
      <button type="button" onClick={onZoomOut} aria-label="Zoom out">
        −
      </button>
      <button
        type="button"
        className="canvas-controls-zoom"
        onClick={onReset}
        aria-label="Reset zoom and pan"
        title="Reset view"
      >
        {formatZoomPercent(viewport.zoom)}
      </button>
      <button type="button" onClick={onZoomIn} aria-label="Zoom in">
        +
      </button>
    </div>
  );
}
