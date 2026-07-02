from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from livekit.agents import Agent, AgentSession

    from app.agent.whiteboard import SessionData


def resolve_agent_session(agent: Agent) -> AgentSession | None:
    """Return bound session without triggering ``Agent.session`` when unbound."""
    sess = getattr(agent, "_fake_session_for_tests", None)
    if sess is None:
        activity = getattr(agent, "_activity", None)
        sess = activity.session if activity is not None else None
    return sess


def resolve_session_data(agent: Agent) -> SessionData | None:
    from app.agent.whiteboard import SessionData

    sess = resolve_agent_session(agent)
    if sess is None:
        return None
    data = getattr(sess, "userdata", None)
    return data if isinstance(data, SessionData) else None
