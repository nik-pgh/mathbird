"""Per-room whiteboard surface for the voice agent.

Public surface intentionally narrow:

* :class:`BoardState` — mutable per-room cache of the latest user-board reading.
* :func:`publish_ai_board` — server → clients update on the ``ai_board`` topic.
* :func:`install_user_board_listener` — wires the room's data channel into a
  debounced :class:`BoardReader` pipeline that updates ``BoardState``.
* :func:`get_board_reader` — factory selected by ``BOARD_READER`` env var.
* Message schemas (``AiBoardUpdate``, ``UserBoardSnapshot``) — wire format on
  the LiveKit data channel.
"""

from .messages import (
    AI_BOARD_TOPIC,
    USER_BOARD_TOPIC,
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

__all__ = [
    "AI_BOARD_TOPIC",
    "USER_BOARD_TOPIC",
    "AiBoardItem",
    "AiBoardPlot",
    "AiBoardShape",
    "AiBoardText",
    "AiBoardUpdate",
    "BoardReader",
    "BoardState",
    "UserBoardSnapshot",
    "get_board_reader",
    "publish_ai_board",
]
