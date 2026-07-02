"""Tests for agent session access helpers."""

from __future__ import annotations

from dataclasses import dataclass

from livekit.agents import Agent

from app.agent.turn_context.session import resolve_agent_session, resolve_session_data
from app.agent.whiteboard import BoardCache, BoardState, SessionData


@dataclass
class _FakeSession:
    userdata: object


class _FakeActivity:
    def __init__(self, session: object) -> None:
        self.session = session


def test_resolve_agent_session_returns_fake_session_for_tests() -> None:
    fake = _FakeSession(userdata=None)
    agent = Agent(instructions="test")
    agent._fake_session_for_tests = fake  # type: ignore[attr-defined]

    assert resolve_agent_session(agent) is fake


def test_resolve_agent_session_returns_none_when_no_activity() -> None:
    agent = Agent(instructions="test")

    assert resolve_agent_session(agent) is None


def test_resolve_session_data_returns_session_data_from_userdata() -> None:
    data = SessionData(board_state=BoardState(), board_cache=BoardCache())
    fake = _FakeSession(userdata=data)
    agent = Agent(instructions="test")
    agent._fake_session_for_tests = fake  # type: ignore[attr-defined]

    assert resolve_session_data(agent) is data


def test_resolve_session_data_returns_none_when_userdata_is_not_session_data() -> None:
    fake = _FakeSession(userdata={"not": "session data"})
    agent = Agent(instructions="test")
    agent._fake_session_for_tests = fake  # type: ignore[attr-defined]

    assert resolve_session_data(agent) is None


def test_resolve_agent_session_falls_back_to_activity_session() -> None:
    fake = _FakeSession(userdata=None)
    agent = Agent(instructions="test")
    agent._activity = _FakeActivity(fake)  # type: ignore[attr-defined]

    assert resolve_agent_session(agent) is fake
