"""``WhiteboardAgent.on_user_turn_completed`` mutates the per-turn chat context
in place, splicing in the latest reading from ``BoardState``. We exercise that
behavior without standing up a real ``AgentSession`` — we instantiate the
subclass and call the hook directly with a real ``ChatContext``.
"""

from __future__ import annotations

import time

from livekit.agents.llm import ChatContext, ChatMessage

from app.agent.whiteboard.state import BoardState
from app.agent.whiteboard_agent import WhiteboardAgent


def _user_message(text: str) -> ChatMessage:
    return ChatMessage(role="user", content=[text])


async def test_no_reading_means_no_injection() -> None:
    state = BoardState()
    agent = WhiteboardAgent(instructions="be a tutor", board_state=state)
    ctx = ChatContext.empty()

    await agent.on_user_turn_completed(ctx, _user_message("help"))

    # Nothing injected — context still empty (the framework adds the user
    # message itself in a later step, not in this hook).
    assert ctx.items == []


async def test_reading_is_injected_as_system_message() -> None:
    state = BoardState()
    state.user_text = "2x + 3 = 9"
    state.is_blank = False
    state.refreshed_at = time.time() - 1.0  # 1 second ago

    agent = WhiteboardAgent(instructions="be a tutor", board_state=state)
    ctx = ChatContext.empty()

    await agent.on_user_turn_completed(ctx, _user_message("what should I do?"))

    assert len(ctx.items) == 1
    injected = ctx.items[0]
    assert getattr(injected, "role", None) == "system"
    body = injected.content[0] if isinstance(injected.content, list) else injected.content
    assert "user whiteboard" in body.lower()
    assert "2x + 3 = 9" in body


async def test_blank_board_still_emits_status_line() -> None:
    state = BoardState()
    state.record_empty()  # is_blank=True, refreshed_at set

    agent = WhiteboardAgent(instructions="be a tutor", board_state=state)
    ctx = ChatContext.empty()

    await agent.on_user_turn_completed(ctx, _user_message("ok"))

    assert len(ctx.items) == 1
    body = ctx.items[0].content[0]
    assert "blank" in body.lower() or "empty" in body.lower()
