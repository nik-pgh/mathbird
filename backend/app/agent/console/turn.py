"""Text-turn helpers for local console and YAML simulators.

``AgentSession.run()`` / ``generate_reply()`` bypass the voice pipeline's
end-of-turn hook. Production voice sessions call ``on_user_turn_completed``
from STT; typed local runs must invoke it explicitly so progress injection
and grader-driven state updates match production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from livekit.agents.llm import ChatContext, ChatMessage
from livekit.agents.voice.run_result import RunResult

from app.agent.turn_context.prepare import prepare_turn_context
from app.agent.turn_context.types import TurnContextSnapshot

if TYPE_CHECKING:
    from livekit.agents import AgentSession

    from app.agent.whiteboard_agent import WhiteboardAgent


@dataclass(frozen=True)
class PreparedTurn:
    turn_ctx: ChatContext
    user_message: ChatMessage
    snapshot: TurnContextSnapshot


@dataclass
class TurnRunResult:
    run: RunResult
    snapshot: TurnContextSnapshot


async def prepare_user_turn(agent: WhiteboardAgent, user_input: str) -> PreparedTurn:
    turn_ctx = agent.chat_ctx.copy()
    user_message = ChatMessage(role="user", content=[user_input])
    snapshot = await prepare_turn_context(agent, turn_ctx, user_message)
    return PreparedTurn(turn_ctx, user_message, snapshot)


async def run_text_turn(
    session: AgentSession,
    agent: WhiteboardAgent,
    user_input: str,
) -> TurnRunResult:
    """Run one typed user turn through ``prepare_turn_context`` then the LLM."""
    prepared = await prepare_user_turn(agent, user_input)

    if session._global_run_state is not None and not session._global_run_state.done():
        raise RuntimeError("nested runs are not supported")

    run_state = RunResult(user_input=user_input, output_type=None)
    session._global_run_state = run_state
    handle = session.generate_reply(
        user_input=prepared.user_message,
        chat_ctx=prepared.turn_ctx,
        input_modality="text",
    )
    run_state._watch_handle(handle)
    return TurnRunResult(run=run_state, snapshot=prepared.snapshot)
