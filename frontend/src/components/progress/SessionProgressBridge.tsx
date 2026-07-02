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
  const { syllabus, error } = useSyllabus(activeDocId);

  if (error) {
    return (
      <aside className="roadmap-error" role="alert">
        Couldn&apos;t load syllabus: {error}
      </aside>
    );
  }

  if (!syllabus) {
    return null;
  }

  return (
    <ProgressSnapshotProvider snapshot={snapshot}>
      <RoadmapProgressPanel syllabus={syllabus} />
    </ProgressSnapshotProvider>
  );
}
