import { useEffect, useState } from "react";
import { fetchDocumentSyllabus } from "../../lib/api";
import type { Syllabus } from "../../lib/syllabus";

export function useSyllabus(docId: string | null) {
  const [syllabus, setSyllabus] = useState<Syllabus | null>(null);

  useEffect(() => {
    if (!docId) {
      setSyllabus(null);
      return;
    }

    let cancelled = false;

    fetchDocumentSyllabus(docId)
      .then((loaded) => {
        if (!cancelled) {
          setSyllabus(loaded);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSyllabus(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [docId]);

  return syllabus;
}
