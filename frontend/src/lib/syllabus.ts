/** Mirrors ``backend/app/syllabus/models.py`` — hand-synced, no codegen. */

export interface SyllabusProblem {
  id: string;
  kind: "exercise" | "example";
  label: string;
  block_id: string;
  page_number: number;
  printed_page_number?: number;
  exercise_number?: string;
  example_number?: string;
}

export interface SyllabusConcept {
  id: string;
  title: string;
  block_ids?: string[];
  problems: SyllabusProblem[];
}

export interface SyllabusChapter {
  id: string;
  number: number | null;
  title: string;
  concepts: SyllabusConcept[];
}

export interface Syllabus {
  doc_id: string;
  version?: 1;
  built_at: string;
  chapters: SyllabusChapter[];
}
