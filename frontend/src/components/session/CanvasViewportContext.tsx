import { createContext, useContext, type ReactNode } from "react";
import type { Point, ViewportState } from "./workspaceTypes";

export interface CanvasViewportContextValue {
  viewport: ViewportState;
  isSpacePan: boolean;
  clientToWorld: (clientX: number, clientY: number) => Point;
}

const CanvasViewportContext = createContext<CanvasViewportContextValue | null>(null);

export function CanvasViewportProvider({
  value,
  children,
}: {
  value: CanvasViewportContextValue;
  children: ReactNode;
}) {
  return (
    <CanvasViewportContext.Provider value={value}>
      {children}
    </CanvasViewportContext.Provider>
  );
}

export function useCanvasViewportContext(): CanvasViewportContextValue {
  const ctx = useContext(CanvasViewportContext);
  if (!ctx) {
    throw new Error("useCanvasViewportContext must be used within CanvasViewport");
  }
  return ctx;
}
