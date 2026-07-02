from __future__ import annotations

from livekit.agents.llm import ChatContext

from app.agent.turn_context.types import (
    InjectionBlock,
    TurnContextSnapshot,
    classify_injection_kind,
)


def snapshot_from_turn_ctx(turn_ctx: ChatContext) -> TurnContextSnapshot:
    """Collect system-role messages from turn_ctx as InjectionBlocks."""
    blocks: list[InjectionBlock] = []
    for item in turn_ctx.items:
        if item.type != "message" or item.role != "system":
            continue
        content = item.text_content
        if not content:
            continue
        blocks.append(InjectionBlock(kind=classify_injection_kind(content), content=content))
    return TurnContextSnapshot(injections=tuple(blocks))
