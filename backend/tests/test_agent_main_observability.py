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

    class FakeSession:
        async def start(self, **_kwargs) -> None:
            events.append("session_started")

        async def generate_reply(self, **_kwargs) -> None:
            events.append("reply_generated")

    class FakeBundle:
        session = FakeSession()
        agent = object()
        listener = SimpleNamespace(aclose=lambda: None)
        session_data = SimpleNamespace(progress_engine=None)

    async def _fake_build_session_bundle(**_kwargs):
        events.append("session_created")
        return FakeBundle()

    async def _fake_resolve_session_identity(_ctx, _settings):
        events.append("resolve_identity")
        return None, None

    monkeypatch.setattr(main, "build_session_bundle", _fake_build_session_bundle)
    monkeypatch.setattr(main, "resolve_session_identity", _fake_resolve_session_identity)

    class FakeContext:
        room = SimpleNamespace(name="test-room")

        async def connect(self) -> None:
            events.append("connect")

        def add_shutdown_callback(self, _callback) -> None:
            events.append("shutdown_callback")

    await main.entrypoint(FakeContext())  # type: ignore[arg-type]

    assert setup_calls == ["setup"]
    assert events[0] == "setup"
    assert "connect" in events
    assert "session_started" in events
    assert "reply_generated" in events
