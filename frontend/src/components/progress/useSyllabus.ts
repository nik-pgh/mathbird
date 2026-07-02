import { useEffect, useState } from "react";
import { fetchDocumentSyllabus } from "../../lib/api";
import type { Syllabus } from "../../lib/syllabus";

export function useSyllabus(docId: string | null) {
  const [syllabus, setSyllabus] = useState<Syllabus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) {
      setSyllabus(null);
      setError(null);
      return;
    }

    let cancelled = false;

    fetchDocumentSyllabus(docId)
      .then((loaded) => {
        if (!cancelled) {
          setSyllabus(loaded);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setSyllabus(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [docId]);

  return { syllabus, error };
}
