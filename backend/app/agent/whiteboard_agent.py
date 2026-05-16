"""``Agent`` subclass that knows how to inject the latest user-board reading
into every LLM turn.

The installed ``livekit-agents`` version exposes per-turn context mutation via
``Agent.on_user_turn_completed(turn_ctx, new_message)`` (see
``.venv/.../livekit/agents/voice/agent.py:247``). The framework hands us a
*mutable copy* of the chat context that is then handed to the LLM for that
single turn — so appending a synthetic system message here is the cheapest
way to give the agent up-to-date situational awareness without polluting the
persistent ``Agent.chat_ctx``.
"""

from __future__ import annotations

from typing import Any

from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage

from app.agent.whiteboard.state import BoardState


class WhiteboardAgent(Agent):
    def __init__(self, *, board_state: BoardState, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._board_state = board_state

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,  # noqa: ARG002 — required by the framework hook
    ) -> None:
        state = self._board_state
        if state.refreshed_at is None:
            return

        age = state.age_seconds()
        age_str = f"{age:.0f}s ago" if age is not None else "just now"

        if state.is_blank:
            body = f"[user whiteboard (refreshed {age_str}): blank]"
        else:
            body = (
                f"[user whiteboard (refreshed {age_str}):\n"
                f"{state.user_text}\n]"
            )

        turn_ctx.add_message(role="system", content=body)
