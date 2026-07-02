from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.turn_context.types import InjectionBlock, classify_injection_kind

if TYPE_CHECKING:
    from app.agent.whiteboard.state import BoardState
    from app.progress.engine import ProgressEngine


class TurnContextBuilder:
    def __init__(
        self,
        *,
        board_state: BoardState,
        progress_engine: ProgressEngine | None,
    ) -> None:
        self._board_state = board_state
        self._progress_engine = progress_engine

    def board_injection(self) -> InjectionBlock | None:
        state = self._board_state
        if state.refreshed_at is None:
            return None

        age = state.age_seconds()
        age_str = f"{age:.0f}s ago" if age is not None else "just now"

        if state.is_blank:
            body = f"[user whiteboard (refreshed {age_str}): blank]"
        else:
            body = f"[user whiteboard (refreshed {age_str}):\n{state.user_text}\n]"

        return InjectionBlock(kind=classify_injection_kind(body), content=body)

    def progress_injection(self) -> InjectionBlock | None:
        if self._progress_engine is None:
            return None

        content = self._progress_engine.format_injection()
        return InjectionBlock(kind=classify_injection_kind(content), content=content)

    def base_injections(self) -> tuple[InjectionBlock, ...]:
        blocks: list[InjectionBlock] = []
        board = self.board_injection()
        if board is not None:
            blocks.append(board)
        progress = self.progress_injection()
        if progress is not None:
            blocks.append(progress)
        return tuple(blocks)
