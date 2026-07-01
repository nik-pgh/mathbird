"""Tests for ``build_session_bundle`` wiring and guardrails."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from app.agent.session_factory import build_session_bundle
from app.config import Settings
from app.progress.engine import ProgressEngine
from app.progress.models import ProgressState
from app.syllabus.models import Chapter, Concept, Problem, Syllabus


@dataclass
class _FakeRoom:
    handlers: dict[str, list[Callable]] = field(default_factory=dict)

    def on(self, event: str, handler: Callable | None = None):
        if handler is None:
            def _decorator(h: Callable) -> Callable:
                self.handlers.setdefault(event, []).append(h)
                return h

            return _decorator
        self.handlers.setdefault(event, []).append(handler)
        return handler


def _syllabus() -> Syllabus:
    return Syllabus(
        doc_id="doc-1",
        built_at="2026-06-19T00:00:00+00:00",
        chapters=[
            Chapter(
                id="ch-1",
                number=1,
                title="Chapter 1",
                concepts=[
                    Concept(
                        id="ch-1-c-a",
                        title="Concept A",
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b1",
                                page_number=1,
                            ),
                        ],
                    )
                ],
            )
        ],
    )


def _engine() -> ProgressEngine:
    state = ProgressState(user_id="user-1", doc_id="doc-1", updated_at="2026-06-19T00:00:00+00:00")
    return ProgressEngine(syllabus=_syllabus(), state=state)


@pytest.mark.asyncio
async def test_build_session_bundle_warns_when_progress_loaded_with_null_grader(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _fake_load_progress_engine(user_id: str, doc_id: str):
        return _syllabus(), _engine()

    monkeypatch.setattr(
        "app.agent.session_factory._load_progress_engine",
        _fake_load_progress_engine,
    )
    monkeypatch.setattr("app.agent.session_factory.build_llm", lambda _settings: object())

    settings = Settings(_env_file=None, grader="null")

    with caplog.at_level(logging.WARNING, logger="mathbird.agent"):
        await build_session_bundle(
            room=_FakeRoom(),
            settings=settings,
            user_id="user-1",
            active_doc_id="doc-1",
            text_only=True,
        )

    assert any(
        "Progress tracking loaded but GRADER=null" in record.message
        for record in caplog.records
    )
