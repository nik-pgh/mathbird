"""Knowledge-tracing state machine over a syllabus tree.

Both concepts and problems are trackable: a node id is a concept id or a
problem id. Mastery is ordinal (:data:`~app.progress.models.MasteryLevel`) so
partial progress is observable. Levels move monotonically upward by default
(``set_level``); explicit ``force`` allows corrections.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.progress.messages import (
    ConceptProgressSnapshot,
    ProblemProgressSnapshot,
    SessionProgressUpdate,
)
from app.progress.models import (
    FocusPointer,
    MasteryLevel,
    NodeProgress,
    ProgressState,
    ProgressSummary,
    Recommendation,
    level_rank,
    max_level,
)
from app.syllabus.models import Problem, Syllabus

if TYPE_CHECKING:
    from app.agent.grader.base import GradeResult, NodeUpdate

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def iter_problem_pointers(syllabus: Syllabus) -> list[tuple[FocusPointer, Problem]]:
    """Flat ordered list of (focus pointer, problem) over the whole syllabus."""
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


def _iter_node_pointers(syllabus: Syllabus) -> list[tuple[FocusPointer, str]]:
    """Flat ordered list of (pointer, node_id) over ALL trackable nodes.

    Concepts and problems alike, in syllabus order (a concept precedes its
    problems). Used for summary counts and next-suggestion advancement so a
    problem-poor doc (e.g. an expository chapter) still has trackable surface
    area and a meaningful "next" pointer.

    Placeholder concepts — those with no problems AND no content block_ids
    (builder artifacts from bare chapter/section headings) are skipped; they
    carry no learnable content and would otherwise pollute the node count and
    lead the "next" pointer.
    """
    ordered: list[tuple[FocusPointer, str]] = []
    for chapter in syllabus.chapters:
        for concept in chapter.concepts:
            is_placeholder = not concept.problems and not concept.block_ids
            if not is_placeholder:
                ordered.append(
                    (
                        FocusPointer(
                            chapter_id=chapter.id, concept_id=concept.id, problem_id=""
                        ),
                        concept.id,
                    )
                )
            for problem in concept.problems:
                ordered.append(
                    (
                        FocusPointer(
                            chapter_id=chapter.id,
                            concept_id=concept.id,
                            problem_id=problem.id,
                        ),
                        problem.id,
                    )
                )
    return ordered


def _find_pointer(syllabus: Syllabus, problem_id: str) -> FocusPointer | None:
    for pointer, _problem in iter_problem_pointers(syllabus):
        if pointer.problem_id == problem_id:
            return pointer
    return None


def _node_label(syllabus: Syllabus, pointer: FocusPointer) -> str:
    """Human label for the focused node: problem label when set, else concept title."""
    if pointer.problem_id:
        for chapter in syllabus.chapters:
            if chapter.id != pointer.chapter_id:
                continue
            for concept in chapter.concepts:
                if concept.id != pointer.concept_id:
                    continue
                for problem in concept.problems:
                    if problem.id == pointer.problem_id:
                        return problem.label
    return _concept_title(syllabus, pointer)


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
    """State machine over ``Syllabus`` + ``ProgressState``.

    The engine is deterministic and LLM-free: it mutates state in response to
    tool calls / grader updates and computes derived values (summary, next
    suggestion, recommendation). Recommendation logic lives in
    :meth:`recommend` (Phase C); this module only carries the data plumbing.
    """

    def __init__(self, *, syllabus: Syllabus, state: ProgressState) -> None:
        self._syllabus = syllabus
        self._state = state
        self._ordered = iter_problem_pointers(syllabus)
        self._ordered_nodes = _iter_node_pointers(syllabus)
        self._concepts_by_id = {
            concept.id: (chapter, concept)
            for chapter in syllabus.chapters
            for concept in chapter.concepts
        }
        self._problems_by_id = {
            problem.id: (chapter, concept, problem)
            for chapter in syllabus.chapters
            for concept in chapter.concepts
            for problem in concept.problems
        }
        if self._state.focus is None:
            self._state.next_suggestion = self._first_unmastered_pointer()

    @property
    def state(self) -> ProgressState:
        return self._state

    @property
    def syllabus(self) -> Syllabus:
        return self._syllabus

    # ------------------------------------------------------------------ identity

    def is_problem(self, node_id: str) -> bool:
        return node_id in self._problems_by_id

    def is_concept(self, node_id: str) -> bool:
        return node_id in self._concepts_by_id

    def _resolve_node(self, node_id: str) -> tuple[str, str, str, str]:
        """Return ``(chapter_id, concept_id, problem_id_or_empty, kind)``.

        ``kind`` is ``"problem"`` or ``"concept"``. Raises ``ValueError`` for
        unknown ids so callers fail loudly rather than silently no-op'ing.
        """
        entry = self._problems_by_id.get(node_id)
        if entry is not None:
            chapter, concept, _problem = entry
            return chapter.id, concept.id, node_id, "problem"
        entry = self._concepts_by_id.get(node_id)
        if entry is not None:
            chapter, concept = entry
            return chapter.id, concept.id, "", "concept"
        raise ValueError(f"Unknown node id: {node_id}")

    def _pointer_for(self, node_id: str) -> FocusPointer:
        chapter_id, concept_id, problem_id, _kind = self._resolve_node(node_id)
        return FocusPointer(
            chapter_id=chapter_id, concept_id=concept_id, problem_id=problem_id
        )

    # ------------------------------------------------------------------- levels

    def effective_level(self, node_id: str) -> MasteryLevel:
        """Observed level of a node.

        For a problem this is its stored level. For a concept, the floor is
        the max of its own stored level and the highest child problem level
        (so introducing it, or working any problem in it, lifts it off
        ``not_started``); but mastery is gated on ALL child problems being
        mastered (a concept with one mastered and one unmastered problem is
        not yet mastered). A concept with no problems uses the floor directly.
        """
        node = self._state.nodes.get(node_id)
        own = node.level if node is not None else "not_started"
        if self.is_problem(node_id):
            return own
        child_levels = self._child_problem_levels(node_id)
        if not child_levels:
            return own
        floor = max_level(own, *child_levels)
        if floor == "mastered" and not all(cl == "mastered" for cl in child_levels):
            # Promoted to mastered by aggregation, but not every child is
            # mastered yet → cap at proficient.
            return "proficient"
        return floor

    def _child_problem_levels(self, concept_id: str) -> list[MasteryLevel]:
        entry = self._concepts_by_id.get(concept_id)
        if entry is None:
            return []
        _chapter, concept = entry
        levels: list[MasteryLevel] = []
        for problem in concept.problems:
            node = self._state.nodes.get(problem.id)
            levels.append(node.level if node is not None else "not_started")
        return levels

    def set_level(
        self,
        node_id: str,
        level: MasteryLevel,
        *,
        note: str | None = None,
        force: bool = False,
    ) -> NodeProgress:
        """Set the level of a node.

        Monotonic by default: the level only moves *up*. Pass ``force=True``
        to allow corrections (e.g. the grader revising an over-optimistic
        earlier judgment). ``note`` is appended to ``notes`` when provided.
        """
        self._resolve_node(node_id)  # validate
        node = self._state.nodes.setdefault(node_id, NodeProgress())
        if not force and level_rank(level) < level_rank(node.level):
            return node  # refuse to lower without force
        node.level = level
        node.updated_at = _now_iso()
        if note:
            node.notes = f"{node.notes}\n{note}".strip() if node.notes else note
        if level in {"proficient", "mastered"}:
            node.solved = True
        if level == "mastered":
            node.explained = True
        self._state.updated_at = _now_iso()
        return node

    def record_misconception(self, node_id: str, text: str) -> NodeProgress:
        self._resolve_node(node_id)
        node = self._state.nodes.setdefault(node_id, NodeProgress())
        text = text.strip()
        if text and text not in node.misconceptions:
            node.misconceptions.append(text)
        node.updated_at = _now_iso()
        self._state.updated_at = _now_iso()
        return node

    def clear_misconceptions(self, node_id: str) -> NodeProgress:
        node = self._state.nodes.get(node_id)
        if node is not None and node.misconceptions:
            node.misconceptions.clear()
            node.updated_at = _now_iso()
            self._state.updated_at = _now_iso()
        return node or self._state.nodes.setdefault(node_id, NodeProgress())

    def record_hint(self, node_id: str) -> NodeProgress:
        self._resolve_node(node_id)
        node = self._state.nodes.setdefault(node_id, NodeProgress())
        node.hints_given += 1
        node.updated_at = _now_iso()
        self._state.updated_at = _now_iso()
        return node

    # ----------------------------------------------------------- focus / mastery

    def set_focus(self, node_id: str) -> None:
        """Focus the session on a concept or problem.

        A concept focus also bumps the concept's level to at least
        ``introduced``. A problem focus bumps it to at least ``practicing``.
        """
        chapter_id, concept_id, problem_id, kind = self._resolve_node(node_id)
        self._state.focus = FocusPointer(
            chapter_id=chapter_id, concept_id=concept_id, problem_id=problem_id
        )
        if kind == "concept":
            self.set_level(node_id, "introduced")
        else:
            self.set_level(node_id, "practicing")
        self._state.updated_at = _now_iso()

    def apply_grade_result(self, result: GradeResult) -> bool:
        """Apply a grader result as the single engine write path."""
        changed = False
        if result.set_focus_node_id:
            try:
                self.set_focus(result.set_focus_node_id)
                changed = True
            except ValueError:
                logger.warning(
                    "grader referenced unknown node id: %s",
                    result.set_focus_node_id,
                )
        for update in result.updates:
            try:
                if self._apply_node_update(update):
                    changed = True
            except ValueError:
                logger.warning("grader referenced unknown node id: %s", update.node_id)
        return changed

    def _apply_node_update(self, update: NodeUpdate) -> bool:
        """Apply one graded update; return True if it changed state."""
        before = self.effective_level(update.node_id)
        if update.clear_misconceptions:
            self.clear_misconceptions(update.node_id)
        for text in update.misconception_additions:
            self.record_misconception(update.node_id, text)
        if update.hint_given:
            self.record_hint(update.node_id)
        if update.level is not None:
            self.set_level(
                update.node_id,
                update.level,
                note=update.note or None,
                force=update.force,
            )
        elif update.note:
            # Note-only update: touch the node so its updated_at moves.
            self.set_level(update.node_id, self.effective_level(update.node_id), note=update.note)
        after = self.effective_level(update.node_id)
        if self.is_problem(update.node_id) and after == "mastered" and before != "mastered":
            self._finalize_problem_mastery(update.node_id)
        return (
            after != before
            or bool(update.misconception_additions)
            or update.clear_misconceptions
            or update.hint_given
        )

    def _finalize_problem_mastery(self, problem_id: str) -> None:
        """Apply mastery side effects when a problem first reaches mastered."""
        pointer = self._pointer_for(problem_id)
        node = self._state.nodes.setdefault(problem_id, NodeProgress())
        node.attempts += 1
        node.solved = True
        node.explained = True
        node.updated_at = _now_iso()
        if self._state.focus is None or self._state.focus.problem_id != problem_id:
            self._state.focus = pointer
        self._state.next_suggestion = self._next_after(pointer)
        self._state.updated_at = _now_iso()

    def record_mastery(self, problem_id: str, *, solved: bool, explained: bool) -> None:
        """Manual mastery tool. Maps the two flags onto the ordinal scale."""
        chapter_id, concept_id, _problem_id, kind = self._resolve_node(problem_id)
        if kind != "problem":
            raise ValueError(f"Not a problem id: {problem_id}")
        pointer = FocusPointer(
            chapter_id=chapter_id, concept_id=concept_id, problem_id=problem_id
        )

        node = self._state.nodes.setdefault(problem_id, NodeProgress())
        node.attempts += 1
        node.solved = solved or node.solved
        node.explained = explained or node.explained
        node.updated_at = _now_iso()

        if self._state.focus is None or self._state.focus.problem_id != problem_id:
            self._state.focus = pointer

        if node.level == "not_started":
            node.level = "practicing"

        # Ordinal mapping: solved ∧ explained → mastered; solved → proficient;
        # otherwise stays at / moves to practicing.
        target: MasteryLevel
        if solved and explained:
            target = "mastered"
        elif solved:
            target = "proficient"
        else:
            target = "practicing"
        if level_rank(target) > level_rank(node.level):
            node.level = target

        if node.level == "mastered":
            self._state.next_suggestion = self._next_after(pointer)

        self._state.updated_at = _now_iso()

    # --------------------------------------------------------------- readouts

    def summary(self) -> ProgressSummary:
        # Count over ALL trackable nodes (concepts + problems), so a
        # problem-poor expository chapter still reports meaningful progress.
        total = len(self._ordered_nodes)
        mastered = 0
        in_progress = 0
        for _pointer, node_id in self._ordered_nodes:
            level = self.effective_level(node_id)
            if level == "mastered":
                mastered += 1
            elif level_rank(level) >= level_rank("introduced"):
                in_progress += 1
        return ProgressSummary(mastered=mastered, in_progress=in_progress, total=total)

    def compute_next_suggestion(self) -> FocusPointer | None:
        if self._state.focus is not None:
            focus_node = self._state.focus.problem_id or self._state.focus.concept_id
            if self._is_mastered(focus_node):
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
            level = self.effective_level(problem.id)
            lines.append(
                f"{problem.id}: {problem.label} ({level}, page {problem.page_number})"
            )
        return lines

    def recommend(self) -> Recommendation:
        """Compute a directive for the tutor from current state.

        Deterministic and rule-based (no LLM) — the grader updates *state*;
        this method turns state into the next action. Precedence is evaluated
        top-down; the first matching rule wins.
        """
        focus = self._state.focus
        # No focus yet: introduce the first unmastered node if there is one.
        if focus is None:
            nxt = self.compute_next_suggestion()
            if nxt is None:
                return Recommendation(
                    intent="hold",
                    rationale="No focus and no remaining material.",
                    directive="Wrap up — the student has finished the material.",
                )
            label = _node_label(self._syllabus, nxt)
            return Recommendation(
                intent="introduce",
                focus_node_id=nxt.problem_id or nxt.concept_id,
                rationale="No focus set; next unmastered node selected.",
                directive=f"Introduce the next topic: {label}. Ask what they already know about it.",
            )

        focus_node_id = focus.problem_id or focus.concept_id
        focus_label = _node_label(self._syllabus, focus)
        level = self.effective_level(focus_node_id)
        node = self._state.nodes.get(focus_node_id, NodeProgress())

        # Mastered → advance to the next node.
        if level == "mastered":
            nxt = self._next_after(focus)
            if nxt is None:
                return Recommendation(
                    intent="hold",
                    focus_node_id=focus_node_id,
                    rationale=f"{focus_label} mastered and no further material.",
                    directive=f"{focus_label} is mastered and nothing remains. Wind down the session.",
                )
            nxt_label = _node_label(self._syllabus, nxt)
            return Recommendation(
                intent="advance",
                focus_node_id=nxt.problem_id or nxt.concept_id,
                rationale=f"{focus_label} mastered.",
                directive=f"{focus_label} is mastered. Move on to {nxt_label} — ask them to set it up.",
            )

        # Open misconceptions on the focus node → address them first.
        if node.misconceptions:
            joined = "; ".join(node.misconceptions)
            return Recommendation(
                intent="review",
                focus_node_id=focus_node_id,
                rationale=f"Open misconceptions on {focus_label}: {joined}",
                directive=(
                    f"Address the misconception on {focus_label} before moving on: {joined}. "
                    "Ask a question that surfaces the error."
                ),
            )

        # Stalled: lots of hints, still practicing → review prerequisites.
        if node.hints_given >= 2 and level == "practicing":
            prereq = self._prerequisite_concept(focus.concept_id)
            if prereq is not None:
                return Recommendation(
                    intent="review",
                    focus_node_id=focus_node_id,
                    rationale=f"{focus_label} stalled after {node.hints_given} hints.",
                    directive=(
                        f"The student is stuck on {focus_label} after {node.hints_given} hints. "
                        f"Step back and review {prereq} before retrying."
                    ),
                )
            # No prerequisite to fall back to — still review, but reframe.
            return Recommendation(
                intent="review",
                focus_node_id=focus_node_id,
                rationale=f"{focus_label} stalled after {node.hints_given} hints (no prerequisite).",
                directive=(
                    f"The student is stuck on {focus_label} after {node.hints_given} hints. "
                    "Break the problem into a smaller sub-step and ask about just that part."
                ),
            )

        # Proficient but not mastered → ask for an explanation to seal it.
        if level == "proficient":
            return Recommendation(
                intent="reinforce",
                focus_node_id=focus_node_id,
                rationale=f"{focus_label} solved but not explained.",
                directive=(
                    f"The student solved {focus_label} correctly. Ask them to explain *why* it works "
                    "in their own words before recording mastery."
                ),
            )

        # Default: keep working the current focus.
        return Recommendation(
            intent="continue",
            focus_node_id=focus_node_id,
            rationale=f"{focus_label} at {level}.",
            directive=f"Continue working {focus_label}. Ask one guiding question.",
        )

    def _prerequisite_concept(self, concept_id: str) -> str | None:
        """Title of the concept immediately before this one in the same chapter."""
        for chapter in self._syllabus.chapters:
            ids = [c.id for c in chapter.concepts]
            if concept_id in ids:
                idx = ids.index(concept_id)
                if idx > 0:
                    return chapter.concepts[idx - 1].title
        return None

    def snapshot_update(self) -> SessionProgressUpdate:
        """Wire snapshot carrying the full ordinal level set on problems and
        a concept-level ``concepts`` row per trackable concept."""
        summary = self.summary()
        nodes: list[ProblemProgressSnapshot] = []
        for pointer, problem in self._ordered:
            level = self.effective_level(problem.id)
            node = self._state.nodes.get(problem.id)
            attempts = node.attempts if node is not None else 0
            nodes.append(
                ProblemProgressSnapshot(
                    problem_id=problem.id,
                    chapter_id=pointer.chapter_id,
                    concept_id=pointer.concept_id,
                    label=problem.label,
                    status=level,
                    attempts=attempts,
                )
            )
        concepts = [
            ConceptProgressSnapshot(
                concept_id=concept.id,
                chapter_id=chapter.id,
                label=concept.title,
                level=self.effective_level(concept.id),
                has_open_misconceptions=bool(
                    self._state.nodes.get(concept.id, NodeProgress()).misconceptions
                ),
            )
            for chapter in self._syllabus.chapters
            for concept in chapter.concepts
            if concept.problems or concept.block_ids  # skip placeholder concepts
        ]
        return SessionProgressUpdate(
            op="snapshot",
            focus=self._state.focus,
            next_suggestion=self._state.next_suggestion,
            summary=summary,
            nodes=nodes,
            concepts=concepts,
        )

    def format_injection(self) -> str:
        summary = self.summary()
        focus = self._state.focus
        next_label = (
            _node_label(self._syllabus, self._state.next_suggestion)
            if self._state.next_suggestion
            else "none — end of material"
        )
        rec = self.recommend()
        action_block = f"\n[next action]\n{rec.directive}" if rec.directive else ""

        if focus is None:
            return (
                "[session progress]\n"
                f"Progress: {summary.mastered}/{summary.total} topics mastered\n"
                f"Next when ready: {next_label}"
                f"{action_block}"
            )

        node = self._state.nodes.get(focus.problem_id or focus.concept_id, NodeProgress())
        chapter_title = _chapter_title(self._syllabus, focus)
        concept_title = _concept_title(self._syllabus, focus)
        focus_label = _node_label(self._syllabus, focus)
        chapter_mastered = self._chapter_mastered_count(focus.chapter_id)
        chapter_total = self._chapter_total(focus.chapter_id)
        return (
            "[session progress]\n"
            f"Focus: {chapter_title} → {concept_title} → {focus_label} "
            f"({node.level}, attempt {node.attempts})\n"
            f"Progress: {chapter_mastered}/{chapter_total} topics mastered in current chapter\n"
            f"Next when ready: {next_label}"
            f"{action_block}"
        )

    def nearby_levels(self, focus_node_id: str) -> dict[str, MasteryLevel]:
        """Levels for the focus node and its immediate neighbors.

        Gives the grader a focused view (focus problem + siblings in the same
        concept + the parent concept) rather than the entire syllabus.
        """
        levels: dict[str, MasteryLevel] = {}
        entry = self._problems_by_id.get(focus_node_id)
        if entry is not None:
            chapter, concept, problem = entry
            levels[problem.id] = self.effective_level(problem.id)
            levels[concept.id] = self.effective_level(concept.id)
            for sibling in concept.problems:
                if sibling.id != problem.id:
                    levels[sibling.id] = self.effective_level(sibling.id)
            return levels
        entry = self._concepts_by_id.get(focus_node_id)
        if entry is not None:
            chapter, concept = entry
            levels[concept.id] = self.effective_level(concept.id)
            for problem in concept.problems:
                levels[problem.id] = self.effective_level(problem.id)
        return levels

    def focus_context(self, focus_node_id: str) -> str:
        """A short text block describing the focus node and its setting.

        The grader uses this to ground its judgment (what the student is
        working on, where it sits in the syllabus). Returns "" for unknown.
        """
        entry = self._problems_by_id.get(focus_node_id)
        if entry is not None:
            chapter, concept, problem = entry
            return (
                f"Chapter: {chapter.title}\n"
                f"Concept: {concept.title}\n"
                f"Problem: {problem.label} (page {problem.page_number})"
            )
        entry = self._concepts_by_id.get(focus_node_id)
        if entry is not None:
            chapter, concept = entry
            problem_lines = "\n".join(
                f"  - {p.label} (page {p.page_number})" for p in concept.problems
            ) or "  (no concrete problems)"
            return (
                f"Chapter: {chapter.title}\n"
                f"Concept: {concept.title}\n"
                f"Problems:\n{problem_lines}"
            )
        return ""

    # --------------------------------------------------------------- internals

    def _is_mastered(self, node_id: str) -> bool:
        return self.effective_level(node_id) == "mastered"

    def _first_unmastered_pointer(self) -> FocusPointer | None:
        for pointer, node_id in self._ordered_nodes:
            if not self._is_mastered(node_id):
                return pointer
        return None

    def _next_after(self, current: FocusPointer) -> FocusPointer | None:
        seen_current = False
        current_key = current.problem_id or current.concept_id
        for pointer, node_id in self._ordered_nodes:
            if not seen_current:
                if (pointer.problem_id or pointer.concept_id) == current_key:
                    seen_current = True
                continue
            if not self._is_mastered(node_id):
                return pointer
        return None

    def _chapter_total(self, chapter_id: str) -> int:
        return sum(
            1 for pointer, _ in self._ordered_nodes if pointer.chapter_id == chapter_id
        )

    def _chapter_mastered_count(self, chapter_id: str) -> int:
        count = 0
        for pointer, node_id in self._ordered_nodes:
            if pointer.chapter_id != chapter_id:
                continue
            if self._is_mastered(node_id):
                count += 1
        return count


__all__ = [
    "ProgressEngine",
    "iter_problem_pointers",
]
