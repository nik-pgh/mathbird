"""Per-room whiteboard surface for the voice agent.

Public surface intentionally narrow:

* :class:`BoardState` — mutable per-room cache of the latest user-board reading.
* :class:`BoardCache` — mutable per-room cache of the AiBoard's current items.
* :class:`SessionData` — bundles ``BoardState`` and ``BoardCache``; rides on
  ``AgentSession.userdata``.
* :func:`publish_ai_board` — server → clients update on the ``ai_board`` topic.
* :func:`install_user_board_listener` — wires the room's data channel into a
  debounced :class:`BoardReader` pipeline that updates ``BoardState``.
* :func:`get_board_reader` — factory selected by ``BOARD_READER`` env var.
* :class:`BoardExtractor` / :func:`get_board_extractor` — second-LLM seam that
  publishes board items per agent sentence.
* Message schemas (``AiBoardUpdate``, ``UserBoardSnapshot``) — wire format on
  the LiveKit data channel.
"""

from dataclasses import dataclass

from .cache import BoardCache
from .extractor import BoardExtractor, get_board_extractor
from .listener import UserBoardListenerHandle, install_user_board_listener
from .messages import (
    AI_BOARD_TOPIC,
    USER_BOARD_TOPIC,
    AiBoardDiagram,
    AiBoardItem,
    AiBoardPlot,
    AiBoardShape,
    AiBoardText,
    AiBoardUpdate,
    UserBoardSnapshot,
)
from .publisher import publish_ai_board
from .reader import BoardReader, get_board_reader
from .state import BoardState


@dataclass
class SessionData:
    """Bundle ridden on ``AgentSession.userdata``."""

    board_state: BoardState
    board_cache: BoardCache
    active_doc_id: str | None = None


__all__ = [
    "AI_BOARD_TOPIC",
    "USER_BOARD_TOPIC",
    "AiBoardDiagram",
    "AiBoardItem",
    "AiBoardPlot",
    "AiBoardShape",
    "AiBoardText",
    "AiBoardUpdate",
    "BoardCache",
    "BoardExtractor",
    "BoardReader",
    "BoardState",
    "SessionData",
    "UserBoardListenerHandle",
    "UserBoardSnapshot",
    "get_board_extractor",
    "get_board_reader",
    "install_user_board_listener",
    "publish_ai_board",
]
