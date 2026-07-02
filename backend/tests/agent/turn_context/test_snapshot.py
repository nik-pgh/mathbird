"""Tests for snapshot_from_turn_ctx."""

from __future__ import annotations

from livekit.agents.llm import ChatContext

from app.agent.turn_context import snapshot_from_turn_ctx


def test_empty_ctx_yields_empty_injections() -> None:
    ctx = ChatContext.empty()

    snapshot = snapshot_from_turn_ctx(ctx)

    assert snapshot.injections == ()


def test_system_messages_classified_by_prefix() -> None:
    ctx = ChatContext.empty()
    board = "[user whiteboard (refreshed 1s ago):\nx = 2\n]"
    progress = "[session progress]\nfocus: ch-1-p-1"
    textbook = "[textbook excerpt]\nQuadratic formula"
    ctx.add_message(role="system", content=board)
    ctx.add_message(role="system", content=progress)
    ctx.add_message(role="system", content=textbook)

    snapshot = snapshot_from_turn_ctx(ctx)

    assert len(snapshot.injections) == 3
    assert snapshot.injections[0].kind == "board"
    assert snapshot.injections[0].content == board
    assert snapshot.injections[1].kind == "progress"
    assert snapshot.injections[1].content == progress
    assert snapshot.injections[2].kind == "textbook"
    assert snapshot.injections[2].content == textbook


def test_user_and_assistant_messages_ignored() -> None:
    ctx = ChatContext.empty()
    ctx.add_message(role="system", content="[session progress]\nfocus: ch-1-p-1")
    ctx.add_message(role="user", content="what is x?")
    ctx.add_message(role="assistant", content="let's solve it together")
    ctx.add_message(role="system", content="[user whiteboard]\nblank")

    snapshot = snapshot_from_turn_ctx(ctx)

    assert len(snapshot.injections) == 2
    assert snapshot.injections[0].kind == "progress"
    assert snapshot.injections[1].kind == "board"
