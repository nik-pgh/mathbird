import RoadmapProgressPanel from "./RoadmapProgressPanel";
import { ProgressSnapshotProvider } from "./ProgressSnapshotContext";
import { useProgressChannel } from "./useProgressChannel";
import { useSyllabus } from "./useSyllabus";

interface Props {
  activeDocId: string | null;
}

/** Subscribes to session_progress and renders the syllabus roadmap panel. */
export default function SessionProgressBridge({ activeDocId }: Props) {
  const snapshot = useProgressChannel();
  const syllabus = useSyllabus(activeDocId);

  if (!syllabus) {
    return null;
  }

  return (
    <ProgressSnapshotProvider snapshot={snapshot}>
      <RoadmapProgressPanel syllabus={syllabus} />
    </ProgressSnapshotProvider>
  );
}
