"""Turn context snapshot types and session access helpers."""

from .builder import TurnContextBuilder
from .grade import run_grade_turn_safe
from .grading_task import PendingGrader
from .prepare import PreparedTurnContext, prepare_turn_context
from .session import resolve_agent_session, resolve_session_data
from .snapshot import snapshot_from_turn_ctx
from .types import (
    InjectionBlock,
    InjectionKind,
    TurnContextSnapshot,
    classify_injection_kind,
)

__all__ = [
    "InjectionBlock",
    "InjectionKind",
    "PendingGrader",
    "PreparedTurnContext",
    "run_grade_turn_safe",
    "TurnContextBuilder",
    "TurnContextSnapshot",
    "classify_injection_kind",
    "prepare_turn_context",
    "resolve_agent_session",
    "resolve_session_data",
    "snapshot_from_turn_ctx",
]
