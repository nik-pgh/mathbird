"""Knowledge-tracing state persisted per user and document.

Progress is tracked over the syllabus *tree* — both concepts and problems are
trackable units (a concept with no problems can still progress through the
levels). Every node carries a :class:`NodeProgress` entry (created lazily when
first touched). Mastery is an ordinal :data:`MasteryLevel` so partial progress
is observable, rather than the binary ``solved ∧ explained`` cliff.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FocusPointer(BaseModel):
    """Anchors a session on a single trackable node.

    ``problem_id`` is the empty string when the focus is a concept with no
    active problem; otherwise it identifies the problem within ``concept_id``.
    """

    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    concept_id: str
    problem_id: str = ""


# Ordinal mastery scale. Ordering matters: ``_LEVEL_ORDER`` is the single
# source of truth for level comparisons used by the engine (monotonic raises,
# concept aggregation, summary thresholds).
MasteryLevel = Literal["not_started", "introduced", "practicing", "proficient", "mastered"]

_LEVEL_ORDER: dict[str, int] = {
    "not_started": 0,
    "introduced": 1,
    "practicing": 2,
    "proficient": 3,
    "mastered": 4,
}


def level_rank(level: str) -> int:
    """Numeric ordering of a mastery level (0 = untouched, 4 = mastered)."""
    return _LEVEL_ORDER[level]


def max_level(*levels: str) -> str:
    """Return the highest of the given levels (ties resolve to the first max)."""
    best = "not_started"
    best_rank = _LEVEL_ORDER["not_started"]
    for level in levels:
        rank = _LEVEL_ORDER[level]
        if rank > best_rank:
            best, best_rank = level, rank
    return best


# Kept as a backwards-compatible alias. The wire format historically used a
# three-value status; callers that referenced ``ProblemStatus`` keep working.
ProblemStatus = MasteryLevel


class NodeProgress(BaseModel):
    """Per-node learning state. Keyed by node id = concept id *or* problem id."""

    model_config = ConfigDict(extra="forbid")

    level: MasteryLevel = "not_started"
    attempts: int = 0
    solved: bool = False
    explained: bool = False
    hints_given: int = 0
    misconceptions: list[str] = Field(default_factory=list)
    notes: str = ""
    updated_at: str = ""


# Backwards-compatible alias for the pre-refactor persisted entry name.
ProblemProgress = NodeProgress


class ProgressSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mastered: int = 0
    in_progress: int = 0
    total: int = 0


RecommendationIntent = Literal[
    "introduce",
    "continue",
    "review",
    "reinforce",
    "advance",
    "hold",
]


class Recommendation(BaseModel):
    """A directive computed from progress state, injected into the LLM each turn.

    ``intent`` categorizes the pedagogical move; ``directive`` is the
    "NEXT ACTION" text the tutor follows; ``rationale`` explains the state
    that produced it (for tracing/evaluation, not shown to the student).
    """

    model_config = ConfigDict(extra="forbid")

    intent: RecommendationIntent
    focus_node_id: str = ""
    rationale: str = ""
    directive: str = ""


def _migrate_v1_nodes(raw: Any) -> Any:
    """Normalize a v1 ``nodes`` payload to the v2 ``NodeProgress`` shape.

    The pre-refactor ``ProblemProgress`` used ``status`` with three values
    (``not_started``/``in_progress``/``mastered``) and carried only
    ``attempts``/``solved``/``explained``/``updated_at``. We rename
    ``status`` → ``level`` and fold ``in_progress`` into ``practicing`` (a
    student who was actively working has demonstrated *some* engagement);
    ``not_started`` and ``mastered`` map unchanged. Missing fields are filled
    by pydantic defaults when ``NodeProgress`` is validated.
    """
    if not isinstance(raw, dict):
        return raw
    migrated: dict[str, dict[str, Any]] = {}
    for node_id, node in raw.items():
        if isinstance(node, dict):
            node = dict(node)  # shallow copy; we may mutate
            status = node.pop("status", None)
            if "level" not in node and status is not None:
                node["level"] = "practicing" if status == "in_progress" else status
        migrated[node_id] = node
    return migrated


class ProgressState(BaseModel):
    """Per ``(user_id, doc_id)`` student model.

    ``version`` is bumped to 2 by the refactor; loading a v1 payload (no
    ``version`` field) triggers ``_migrate_v1_payload`` transparently.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    doc_id: str
    updated_at: str
    version: int = 2
    focus: FocusPointer | None = None
    next_suggestion: FocusPointer | None = None
    nodes: dict[str, NodeProgress] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_v1_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # A v1 payload has no ``version`` (or version 1). Migrate the nodes in
        # place; the version field is then set by the default.
        version = data.get("version")
        if version is None or version == 1:
            data = dict(data)
            nodes = data.get("nodes")
            # Only touch nodes when there is something to migrate; otherwise
            # leave the key absent so the Field default_factory supplies {}.
            if nodes is not None:
                data["nodes"] = _migrate_v1_nodes(nodes)
            data["version"] = 2
        return data
