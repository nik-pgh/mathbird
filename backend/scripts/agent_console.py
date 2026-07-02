"""Interactive text console with readable tutor output.

Usage (from ``backend/``)::

    uv run python -m scripts.agent_console
    uv run python -m scripts.agent_console -c   # show per-turn LLM context + progress

Type ``exit`` or ``quit`` (or press Ctrl+D) to leave cleanly.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agent.console.loop import run_console
from app.agent.providers import ensure_livekit_plugins_registered


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive tutor text console.")
    parser.add_argument(
        "-c",
        "--show-context",
        action="store_true",
        help=(
            "Show the LLM context nudge before each turn (board + progress injection) "
            "and the progress snapshot after."
        ),
    )
    return parser.parse_args(argv)


def main() -> int:
    ensure_livekit_plugins_registered()
    args = _parse_args()
    try:
        asyncio.run(run_console(show_context=args.show_context))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
