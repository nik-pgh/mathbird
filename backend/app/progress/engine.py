"""Knowledge-tracing state machine over a syllabus tree."""

from __future__ import annotations

from datetime import UTC, datetime

from app.progress.messages import ProblemProgressSnapshot, SessionProgressUpdate
from app.progress.models import FocusPointer, ProblemProgress, ProgressState, ProgressSummary
from app.syllabus.models import Problem, Syllabus


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def iter_problem_pointers(syllabus: Syllabus) -> list[tuple[FocusPointer, Problem]]:
    ordered: list[tuple[FocusPointer, Problem]] = []
    for chapter in syllabus.chapters:
        for concept in chapter.concepts:
            for problem in concept.problems:
                ordered.append(
                    (
                        FocusPointer(
                            chapter_id=chapter.id,
                            concept_id=concept.id,
                            problem_id=problem.id,
                        ),
                        problem,
                    )
                )
    return ordered


def _find_pointer(syllabus: Syllabus, problem_id: str) -> FocusPointer | None:
    for pointer, _problem in iter_problem_pointers(syllabus):
        if pointer.problem_id == problem_id:
            return pointer
    return None


def _problem_label(syllabus: Syllabus, pointer: FocusPointer) -> str:
    for chapter in syllabus.chapters:
        if chapter.id != pointer.chapter_id:
            continue
        for concept in chapter.concepts:
            if concept.id != pointer.concept_id:
                continue
            for problem in concept.problems:
                if problem.id == pointer.problem_id:
                    return problem.label
    return pointer.problem_id


def _chapter_title(syllabus: Syllabus, pointer: FocusPointer) -> str:
    for chapter in syllabus.chapters:
        if chapter.id == pointer.chapter_id:
            return chapter.title
    return pointer.chapter_id


def _concept_title(syllabus: Syllabus, pointer: FocusPointer) -> str:
    for chapter in syllabus.chapters:
        if chapter.id != pointer.chapter_id:
            continue
        for concept in chapter.concepts:
            if concept.id == pointer.concept_id:
                return concept.title
    return pointer.concept_id


class ProgressEngine:
    def __init__(self, *, syllabus: Syllabus, state: ProgressState) -> None:
        self._syllabus = syllabus
        self._state = state
        self._ordered = iter_problem_pointers(syllabus)
        if self._state.focus is None:
            self._state.next_suggestion = self._first_unmastered_pointer()

    @property
    def state(self) -> ProgressState:
        return self._state

    def summary(self) -> ProgressSummary:
        total = len(self._ordered)
        mastered = sum(1 for _pointer, problem in self._ordered if self._is_mastered(problem.id))
        in_progress = sum(
            1
            for node in self._state.nodes.values()
            if node.status == "in_progress"
        )
        return ProgressSummary(mastered=mastered, in_progress=in_progress, total=total)

    def set_focus(self, problem_id: str) -> None:
        pointer = _find_pointer(self._syllabus, problem_id)
        if pointer is None:
            raise ValueError(f"Unknown problem_id: {problem_id}")
        self._state.focus = pointer
        node = self._state.nodes.setdefault(problem_id, ProblemProgress())
        if node.status == "not_started":
            node.status = "in_progress"
        node.updated_at = _now_iso()
        self._state.updated_at = _now_iso()

    def record_mastery(self, problem_id: str, *, solved: bool, explained: bool) -> None:
        pointer = _find_pointer(self._syllabus, problem_id)
        if pointer is None:
            raise ValueError(f"Unknown problem_id: {problem_id}")

        node = self._state.nodes.setdefault(problem_id, ProblemProgress())
        node.attempts += 1
        node.solved = solved
        node.explained = explained
        node.updated_at = _now_iso()

        if self._state.focus is None or self._state.focus.problem_id != problem_id:
            self._state.focus = pointer

        if node.status == "not_started":
            node.status = "in_progress"

        if solved and explained:
            node.status = "mastered"
            self._state.next_suggestion = self._next_after(pointer)
        else:
            node.status = "in_progress"

        self._state.updated_at = _now_iso()

    def compute_next_suggestion(self) -> FocusPointer | None:
        if self._state.focus is not None and self._is_mastered(self._state.focus.problem_id):
            return self._next_after(self._state.focus)
        return self._state.next_suggestion

    def list_problems(
        self,
        *,
        chapter_id: str | None = None,
        concept_id: str | None = None,
    ) -> list[str]:
        lines: list[str] = []
        for pointer, problem in self._ordered:
            if chapter_id and pointer.chapter_id != chapter_id:
                continue
            if concept_id and pointer.concept_id != concept_id:
                continue
            node = self._state.nodes.get(problem.id)
            status = node.status if node else "not_started"
            lines.append(f"{problem.id}: {problem.label} ({status}, page {problem.page_number})")
        return lines

    def snapshot_update(self) -> SessionProgressUpdate:
        summary = self.summary()
        nodes: list[ProblemProgressSnapshot] = []
        for pointer, problem in self._ordered:
            node = self._state.nodes.get(problem.id)
            status = node.status if node is not None else "not_started"
            attempts = node.attempts if node is not None else 0
            nodes.append(
                ProblemProgressSnapshot(
                    problem_id=problem.id,
                    chapter_id=pointer.chapter_id,
                    concept_id=pointer.concept_id,
                    label=problem.label,
                    status=status,
                    attempts=attempts,
                )
            )
        return SessionProgressUpdate(
            op="snapshot",
            focus=self._state.focus,
            next_suggestion=self._state.next_suggestion,
            summary=summary,
            nodes=nodes,
        )

    def format_injection(self) -> str:
        summary = self.summary()
        focus = self._state.focus
        if focus is None:
            next_label = (
                _problem_label(self._syllabus, self._state.next_suggestion)
                if self._state.next_suggestion
                else "none — end of material"
            )
            return (
                "[session progress]\n"
                f"Progress: {summary.mastered}/{summary.total} problems mastered\n"
                f"Next when ready: {next_label}"
            )

        node = self._state.nodes.get(focus.problem_id, ProblemProgress())
        next_label = (
            _problem_label(self._syllabus, self._state.next_suggestion)
            if self._state.next_suggestion
            else "none — end of material"
        )
        chapter_title = _chapter_title(self._syllabus, focus)
        concept_title = _concept_title(self._syllabus, focus)
        problem_label = _problem_label(self._syllabus, focus)
        chapter_mastered = self._chapter_mastered_count(focus.chapter_id)
        chapter_total = self._chapter_total(focus.chapter_id)
        return (
            "[session progress]\n"
            f"Focus: {chapter_title} → {concept_title} → {problem_label} "
            f"({node.status}, attempt {node.attempts})\n"
            f"Progress: {chapter_mastered}/{chapter_total} problems mastered in current chapter\n"
            f"Next when ready: {next_label}"
        )

    def _is_mastered(self, problem_id: str) -> bool:
        node = self._state.nodes.get(problem_id)
        return node is not None and node.status == "mastered"

    def _first_unmastered_pointer(self) -> FocusPointer | None:
        for pointer, problem in self._ordered:
            if not self._is_mastered(problem.id):
                return pointer
        return None

    def _next_after(self, current: FocusPointer) -> FocusPointer | None:
        seen_current = False
        for pointer, problem in self._ordered:
            if not seen_current:
                if pointer.problem_id == current.problem_id:
                    seen_current = True
                continue
            if not self._is_mastered(problem.id):
                return pointer
        return None

    def _chapter_total(self, chapter_id: str) -> int:
        return sum(1 for pointer, _ in self._ordered if pointer.chapter_id == chapter_id)

    def _chapter_mastered_count(self, chapter_id: str) -> int:
        count = 0
        for pointer, problem in self._ordered:
            if pointer.chapter_id != chapter_id:
                continue
            if self._is_mastered(problem.id):
                count += 1
        return count
