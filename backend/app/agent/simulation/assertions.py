"""Check a single turn's ``RunResult`` events against scenario expectations."""

from __future__ import annotations

import json

from livekit.agents.voice.run_result import RunEvent, RunResult

from .scenarios import TurnExpectation


def _assistant_text(events: list[RunEvent]) -> str:
    parts: list[str] = []
    for event in events:
        if event.type != "message":
            continue
        if event.item.role != "assistant":
            continue
        parts.append(event.item.text_content)
    return "\n".join(parts)


def _function_calls(events: list[RunEvent], name: str | None = None) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    for event in events:
        if event.type != "function_call":
            continue
        call_name = event.item.name
        if name is not None and call_name != name:
            continue
        calls.append((call_name, event.item.arguments or ""))
    return calls


def assert_turn_expectations(run: RunResult, expect: TurnExpectation, *, turn_label: str) -> None:
    """Raise ``AssertionError`` with a readable message when expectations fail."""
    events = run.events
    prefix = f"[{turn_label}]"

    for tool_name in expect.tool_calls:
        matching = _function_calls(events, name=tool_name)
        if not matching:
            names = [name for name, _ in _function_calls(events)]
            raise AssertionError(
                f"{prefix} expected tool call {tool_name!r}, got {names or 'none'}"
            )

    if expect.search_query_contains:
        search_calls = _function_calls(events, name="search_documents")
        if not search_calls:
            raise AssertionError(f"{prefix} expected search_documents call")
        args_blob = " ".join(args for _, args in search_calls)
        try:
            parsed = json.loads(search_calls[0][1])
            query = str(parsed.get("query", ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            query = args_blob
        haystack = f"{query} {args_blob}".lower()
        for fragment in expect.search_query_contains:
            if fragment.lower() not in haystack:
                raise AssertionError(
                    f"{prefix} search_documents query missing {fragment!r} (got {query!r})"
                )

    assistant = _assistant_text(events).lower()
    if not assistant and (expect.assistant_contains or expect.assistant_not_contains):
        raise AssertionError(f"{prefix} expected assistant reply, got none")

    for fragment in expect.assistant_contains:
        if fragment.lower() not in assistant:
            raise AssertionError(
                f"{prefix} assistant reply missing {fragment!r}: {_assistant_text(events)!r}"
            )

    for fragment in expect.assistant_not_contains:
        if fragment.lower() in assistant:
            raise AssertionError(
                f"{prefix} assistant reply must not contain {fragment!r}: "
                f"{_assistant_text(events)!r}"
            )
