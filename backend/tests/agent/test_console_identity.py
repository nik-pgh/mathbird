from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.console.identity import prompt_console_identity


@pytest.mark.asyncio
async def test_prompt_skips_when_env_fully_set(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agent.console.identity.sys.stdin.isatty",
        lambda: True,
    )

    user_id, doc_id = await prompt_console_identity(
        SimpleNamespace(sim_interactive=True),
        need_user=False,
        need_doc=False,
    )
    assert user_id is None
    assert doc_id is None


@pytest.mark.asyncio
async def test_prompt_skips_when_not_tty(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agent.console.identity.sys.stdin.isatty",
        lambda: False,
    )

    user_id, doc_id = await prompt_console_identity(
        SimpleNamespace(sim_interactive=True),
        need_user=True,
        need_doc=True,
    )
    assert user_id is None
    assert doc_id is None


@pytest.mark.asyncio
async def test_prompt_doc_selection(monkeypatch) -> None:
    monkeypatch.setattr("app.agent.console.identity.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "app.agent.console.identity.list_document_summaries",
        lambda: _async_docs(),
    )
    inputs = iter(["1"])

    async def _fake_read_line(_prompt: str) -> str:
        return next(inputs)

    monkeypatch.setattr(
        "app.agent.console.identity._read_line",
        _fake_read_line,
    )

    user_id, doc_id = await prompt_console_identity(
        SimpleNamespace(sim_interactive=True),
        need_user=False,
        need_doc=True,
    )

    assert user_id is None
    assert doc_id == "doc-abc"


@pytest.mark.asyncio
async def test_resolve_local_identity_prompts_when_env_incomplete(monkeypatch) -> None:
    from app.agent.console.identity import resolve_local_identity

    async def _fake_prompt(_settings, *, need_user, need_doc):
        assert need_user is True
        assert need_doc is True
        return "picked-user", "picked-doc"

    monkeypatch.setattr(
        "app.agent.console.identity.prompt_console_identity",
        _fake_prompt,
    )

    settings = SimpleNamespace(sim_user_id="", sim_active_doc_id="", sim_interactive=True)

    user_id, doc_id = await resolve_local_identity(settings)  # type: ignore[arg-type]

    assert user_id == "picked-user"
    assert doc_id == "picked-doc"


async def _async_docs():
    from app.documents.catalog import DocumentSummary

    return [
        DocumentSummary(
            doc_id="doc-abc",
            key="doc-abc/book.pdf",
            uri="file:///tmp/book.pdf",
            filename="book.pdf",
            status="indexed",
            syllabus_ready=True,
            size=123,
            content_type="application/pdf",
        )
    ]