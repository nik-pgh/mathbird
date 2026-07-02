"""Run a scripted tutor↔student conversation against the real agent stack.

Usage (from ``backend/``)::

    uv run python -m scripts.simulate_conversation \\
        simulations/scenarios/tutor_greeting.yaml

    uv run python -m scripts.simulate_conversation \\
        simulations/scenarios/problem_help.yaml \\
        --verbose

    uv run python -m scripts.simulate_conversation \\
        simulations/scenarios/progression_demo.yaml \\
        --show-context

Scenario ``user_id`` / ``doc_id`` override ``SIM_USER_ID`` / ``SIM_ACTIVE_DOC_ID``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from livekit import rtc

from app.agent.console.context_view import (
    assistant_reply,
    print_llm_context,
    print_progress_snapshot,
)
from app.agent.console.runtime import local_text_job
from app.agent.console.turn import run_text_turn
from app.agent.console.ui import format_run_event
from app.agent.grader.base import GradeResult
from app.agent.grader.fake import FakeGrader
from app.agent.providers import ensure_livekit_plugins_registered
from app.agent.session_factory import build_session_bundle, send_initial_greeting
from app.agent.simulation import assert_turn_expectations, load_scenario
from app.config import Settings, get_settings

if TYPE_CHECKING:
    from app.agent.whiteboard import SessionData


def _apply_board_text(session_data: SessionData, text: str | None) -> None:
    if not text:
        return
    state = session_data.board_state
    state.user_text = text
    state.is_blank = False
    state.refreshed_at = time.time()


def _scripted_grader_for_scenario(scenario) -> FakeGrader | None:
    has_scripted_results = any(turn.grader_result is not None for turn in scenario.turns)
    if not has_scripted_results:
        return None
    queued_results = [turn.grader_result or GradeResult() for turn in scenario.turns]
    return FakeGrader(queued_results)


async def run_scenario(
    scenario_path: Path,
    *,
    settings: Settings,
    verbose: bool = False,
    show_context: bool = False,
) -> None:
    scenario = load_scenario(scenario_path)
    scripted_grader = _scripted_grader_for_scenario(scenario)
    user_id = scenario.user_id or settings.sim_user_id or None
    active_doc_id = scenario.doc_id or settings.sim_active_doc_id or None

    print(f"Scenario: {scenario.name}", flush=True)
    if user_id or active_doc_id:
        print(f"  identity: user_id={user_id!r} doc_id={active_doc_id!r}", flush=True)

    room = rtc.Room()
    try:
        async with local_text_job(room=room):
            bundle = await build_session_bundle(
                room=room,
                settings=settings,
                user_id=user_id,
                active_doc_id=active_doc_id,
                text_only=True,
                grader=scripted_grader,
            )
            _apply_board_text(bundle.session_data, scenario.board_text)
            engine = bundle.session_data.progress_engine

            await bundle.session.start(agent=bundle.agent, record=False)

            try:
                if show_context and engine is not None:
                    print("\n--- initial context ---", flush=True)
                    print_llm_context(bundle.session_data, engine)

                if scenario.greeting:
                    await send_initial_greeting(
                        bundle.session,
                        has_progress=engine is not None,
                    )
                    if verbose:
                        print(
                            "--- greeting (see assistant reply in turn events) ---",
                            flush=True,
                        )

                for index, turn in enumerate(scenario.turns, start=1):
                    label = f"turn {index}"
                    board_text = (
                        turn.board_text if turn.board_text is not None else scenario.board_text
                    )
                    _apply_board_text(bundle.session_data, board_text)

                    print(f"\n--- {label}: student ---", flush=True)
                    print(turn.student, flush=True)

                    if show_context:
                        print(f"\n--- {label}: context (what the LLM sees) ---", flush=True)
                        print_llm_context(bundle.session_data, engine)

                    run = await run_text_turn(bundle.session, bundle.agent, turn.student)
                    await run

                    if verbose:
                        print(f"--- {label}: events ---", flush=True)
                        for event in run.events:
                            print(
                                json.dumps(format_run_event(event), ensure_ascii=False),
                                flush=True,
                            )

                    if show_context:
                        reply = assistant_reply(run.events)
                        print(f"\n--- {label}: tutor ---", flush=True)
                        if reply.strip():
                            for line in reply.splitlines():
                                print(f"  {line}" if line else "", flush=True)
                        else:
                            print("  (no assistant reply)", flush=True)
                        if engine is not None:
                            print(f"\n--- {label}: progress (after turn) ---", flush=True)
                            print_progress_snapshot(engine)

                    assert_turn_expectations(
                        run,
                        turn.expect,
                        turn_label=label,
                        engine=engine,
                    )
                    print(f"  ✓ {label} expectations passed", flush=True)
            finally:
                await bundle.listener.aclose()
                await bundle.session.aclose()
    finally:
        room.disconnect()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a tutor conversation from YAML.")
    parser.add_argument(
        "scenario",
        type=Path,
        help="Path to a scenario YAML file (e.g. simulations/scenarios/tutor_greeting.yaml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print RunResult events after each turn (raw JSON, deep debugging).",
    )
    parser.add_argument(
        "-c",
        "--show-context",
        action="store_true",
        help=(
            "Show the LLM context nudge before each turn (board + progress injection) "
            "and the progress snapshot after. Pairs with -v."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ensure_livekit_plugins_registered()
    args = _parse_args(argv)
    scenario_path = args.scenario
    if not scenario_path.is_file():
        print(f"Scenario file not found: {scenario_path}", file=sys.stderr)
        return 1

    try:
        asyncio.run(
            run_scenario(
                scenario_path,
                settings=get_settings(),
                verbose=args.verbose,
                show_context=args.show_context,
            )
        )
    except AssertionError as exc:
        print(f"\nSimulation failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    print("\nAll turns passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
