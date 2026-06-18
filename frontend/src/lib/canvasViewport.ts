import type { Point, ViewportState } from "../components/session/workspaceTypes";

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 2.5;
export const DEFAULT_ZOOM = 1;
export const CANVAS_WHEEL_IGNORE_ATTR = "data-canvas-wheel-ignore";

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

export function clientToWorld(
  clientX: number,
  clientY: number,
  boardRect: DOMRect,
  viewport: ViewportState,
): Point {
  return {
    x: (clientX - boardRect.left - viewport.pan.x) / viewport.zoom,
    y: (clientY - boardRect.top - viewport.pan.y) / viewport.zoom,
  };
}

/** Focal point is in board-local screen coordinates (px from board top-left). */
export function zoomAtPoint(
  viewport: ViewportState,
  nextZoom: number,
  focalX: number,
  focalY: number,
): ViewportState {
  const zoom = clampZoom(nextZoom);
  const worldX = (focalX - viewport.pan.x) / viewport.zoom;
  const worldY = (focalY - viewport.pan.y) / viewport.zoom;
  return {
    zoom,
    pan: {
      x: focalX - worldX * zoom,
      y: focalY - worldY * zoom,
    },
  };
}

export function panBy(viewport: ViewportState, deltaX: number, deltaY: number): ViewportState {
  return {
    ...viewport,
    pan: {
      x: viewport.pan.x + deltaX,
      y: viewport.pan.y + deltaY,
    },
  };
}

export function formatZoomPercent(zoom: number): string {
  return `${Math.round(zoom * 100)}%`;
}

export function shouldHandleCanvasWheelTarget(target: EventTarget | null): boolean {
  const maybeElement = target as { closest?: (selector: string) => unknown } | null;
  if (typeof maybeElement?.closest !== "function") return true;
  return !maybeElement.closest(`[${CANVAS_WHEEL_IGNORE_ATTR}]`);
}
