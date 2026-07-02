"""Text-turn helpers for local console and YAML simulators.

``AgentSession.run()`` / ``generate_reply()`` bypass the voice pipeline's
end-of-turn hook. Production voice sessions call ``on_user_turn_completed``
from STT; typed local runs must invoke it explicitly so progress injection
and grader-driven state updates match production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from livekit.agents.llm import ChatMessage
from livekit.agents.voice.run_result import RunResult

if TYPE_CHECKING:
    from livekit.agents import AgentSession

    from app.agent.whiteboard_agent import WhiteboardAgent


async def run_text_turn(
    session: AgentSession,
    agent: WhiteboardAgent,
    user_input: str,
) -> RunResult:
    """Run one typed user turn through ``on_user_turn_completed`` then the LLM."""
    turn_ctx = agent.chat_ctx.copy()
    user_message = ChatMessage(role="user", content=[user_input])
    await agent.on_user_turn_completed(turn_ctx, user_message)

    if session._global_run_state is not None and not session._global_run_state.done():
        raise RuntimeError("nested runs are not supported")

    run_state = RunResult(user_input=user_input, output_type=None)
    session._global_run_state = run_state
    handle = session.generate_reply(
        user_input=user_message,
        chat_ctx=turn_ctx,
        input_modality="text",
    )
    run_state._watch_handle(handle)
    return run_state
