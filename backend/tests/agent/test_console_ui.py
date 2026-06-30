"""Tests for console terminal formatters."""

from app.agent.console.ui import _summarize_tool_args, _truncate


def test_summarize_search_documents_query() -> None:
    args = '{"query": "Example 2.12 solution steps"}'
    assert _summarize_tool_args("search_documents", args) == "Example 2.12 solution steps"


def test_summarize_invalid_json() -> None:
    assert _summarize_tool_args("foo", "not-json") == "not-json"


def test_truncate() -> None:
    assert _truncate("hello", 10) == "hello"
    assert _truncate("hello world", 8) == "hello w…"
