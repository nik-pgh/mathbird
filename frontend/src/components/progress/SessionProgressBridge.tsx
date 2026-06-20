import GrowthTreePanel from "./GrowthTreePanel";
import { ProgressSnapshotProvider } from "./ProgressSnapshotContext";
import { useProgressChannel } from "./useProgressChannel";

/** Subscribes to session_progress and renders the growth-tree panel. */
export default function SessionProgressBridge() {
  const snapshot = useProgressChannel();

  return (
    <ProgressSnapshotProvider snapshot={snapshot}>
      <GrowthTreePanel />
    </ProgressSnapshotProvider>
  );
}
