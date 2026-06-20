from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from app import observability


def _fresh_agent_main(monkeypatch: pytest.MonkeyPatch, setup_calls: list[str]):
    sys.modules.pop("app.agent.main", None)
    monkeypatch.setattr(observability, "setup_phoenix", lambda: setup_calls.append("setup"))
    return importlib.import_module("app.agent.main")


def test_agent_main_does_not_initialize_phoenix_in_worker_parent(monkeypatch) -> None:
    setup_calls: list[str] = []

    _fresh_agent_main(monkeypatch, setup_calls)

    assert setup_calls == []


@pytest.mark.asyncio
async def test_entrypoint_initializes_phoenix_inside_room_job(monkeypatch) -> None:
    setup_calls: list[str] = []
    main = _fresh_agent_main(monkeypatch, setup_calls)
    events: list[str] = []

    monkeypatch.setattr(
        main,
        "setup_phoenix",
        lambda: (setup_calls.append("setup"), events.append("setup")),
    )
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(
            stt_provider="deepgram",
            llm_provider="openai",
            tts_provider="elevenlabs",
            vad_provider="silero",
            board_reader="null",
            board_extractor="null",
            board_reader_interval_seconds=2.0,
            agent_instructions="test instructions",
        ),
    )
    monkeypatch.setattr(main, "get_board_reader", lambda: object())
    monkeypatch.setattr(main, "get_board_extractor", lambda: object())
    monkeypatch.setattr(
        main,
        "install_user_board_listener",
        lambda **_kwargs: SimpleNamespace(aclose=lambda: None),
    )
    monkeypatch.setattr(main, "build_stt", lambda _settings: object())
    monkeypatch.setattr(main, "build_llm", lambda _settings: object())
    monkeypatch.setattr(main, "build_tts", lambda _settings: object())
    monkeypatch.setattr(main, "build_vad", lambda _settings: object())
    monkeypatch.setattr(main, "build_function_tools", lambda **_kwargs: [])
    monkeypatch.setattr(main, "WhiteboardAgent", lambda **_kwargs: object())

    class FakeSession:
        def __init__(self, **_kwargs) -> None:
            events.append("session_created")

        async def start(self, **_kwargs) -> None:
            events.append("session_started")

        async def generate_reply(self, **_kwargs) -> None:
            events.append("reply_generated")

    class FakeContext:
        room = SimpleNamespace(name="test-room")

        async def connect(self) -> None:
            events.append("connect")

        def add_shutdown_callback(self, _callback) -> None:
            events.append("shutdown_callback")

        async def wait_for_participant(self):
            events.append("wait_for_participant")
            return SimpleNamespace(metadata=None)

    monkeypatch.setattr(main, "AgentSession", FakeSession)

    await main.entrypoint(FakeContext())

    assert setup_calls == ["setup"]
    assert events[0] == "setup"
    assert "connect" in events
