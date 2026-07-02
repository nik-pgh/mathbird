"""Tests for console terminal formatters."""

from io import StringIO

from rich.console import Console

from app.agent.console.ui import (
    _format_setup_line,
    _summarize_tool_args,
    _truncate,
    print_banner,
)


def test_summarize_search_documents_query() -> None:
    args = '{"query": "Example 2.12 solution steps"}'
    assert _summarize_tool_args("search_documents", args) == "Example 2.12 solution steps"


def test_summarize_invalid_json() -> None:
    assert _summarize_tool_args("foo", "not-json") == "not-json"


def test_truncate() -> None:
    assert _truncate("hello", 10) == "hello"
    assert _truncate("hello world", 8) == "hello w…"


def test_format_setup_line_without_detail() -> None:
    assert _format_setup_line("Document", None, None) == "Document  [dim]none[/dim]"
    assert "abc123" in _format_setup_line("User", "abc123", None)


def test_print_banner_includes_settings_modes() -> None:
    from types import SimpleNamespace

    buffer = StringIO()
    from app.agent.console import ui as ui_module

    original = ui_module._console
    ui_module._console = Console(file=buffer, highlight=False, width=120)
    try:
        print_banner(
            doc_id="doc-abc",
            user_id="user-xyz",
            doc_filename="book.pdf",
            user_email="student@example.com",
            settings=SimpleNamespace(grader="openai", rag_provider="llamaindex_qdrant"),
        )
    finally:
        ui_module._console = original

    output = buffer.getvalue()
    assert "book.pdf" in output
    assert "student@example.com" in output
    assert "openai" in output
    assert "llamaindex_qdrant" in output
