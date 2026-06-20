import { createContext, useContext, type ReactNode } from "react";
import type { SessionProgressUpdate } from "../../lib/progress";

const ProgressSnapshotContext = createContext<SessionProgressUpdate | null>(null);

export function ProgressSnapshotProvider({
  snapshot,
  children,
}: {
  snapshot: SessionProgressUpdate | null;
  children: ReactNode;
}) {
  return (
    <ProgressSnapshotContext.Provider value={snapshot}>
      {children}
    </ProgressSnapshotContext.Provider>
  );
}

export function useProgressSnapshot() {
  return useContext(ProgressSnapshotContext);
}
