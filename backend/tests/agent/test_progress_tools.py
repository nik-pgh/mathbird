"""Tests for read-only progress function tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.agent.tools import build_function_tools, get_progress
from app.agent.whiteboard import BoardCache, BoardState, SessionData
from app.config import get_settings
from app.progress.engine import ProgressEngine
from app.progress.models import ProgressState
from app.storage import base as storage_mod
from app.syllabus.models import Chapter, Concept, Problem, Syllabus


@dataclass
class _FakeSession:
    userdata: object


@dataclass
class _FakeRunContext:
    session: _FakeSession


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
                        title="A",
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b1",
                                page_number=1,
                            )
                        ],
                    )
                ],
            )
        ],
    )


@pytest.fixture(autouse=True)
def storage_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    yield
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()


def _ctx() -> _FakeRunContext:
    state = ProgressState(user_id="user-1", doc_id="doc-1", updated_at="t")
    engine = ProgressEngine(syllabus=_syllabus(), state=state)
    data = SessionData(
        board_state=BoardState(),
        board_cache=BoardCache(),
        active_doc_id="doc-1",
        user_id="user-1",
        syllabus=_syllabus(),
        progress_engine=engine,
    )
    return _FakeRunContext(session=_FakeSession(userdata=data))


@pytest.mark.asyncio
async def test_get_progress_returns_injection() -> None:
    ctx = _ctx()
    result = await get_progress(ctx)
    assert "[session progress]" in result
    assert "[next action]" in result


def test_build_function_tools_excludes_mutating_progress_tools() -> None:
    tools = build_function_tools(include_progress=True)
    names = {t.__name__ for t in tools}  # type: ignore[attr-defined]
    assert names == {"search_documents", "read_user_board", "get_progress", "list_problems"}
    assert "set_focus" not in names
    assert "record_mastery" not in names
