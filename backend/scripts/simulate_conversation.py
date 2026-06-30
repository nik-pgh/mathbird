"""Run a scripted tutor↔student conversation against the real agent stack.

Usage (from ``backend/``)::

    uv run python -m scripts.simulate_conversation \\
        simulations/scenarios/tutor_greeting.yaml

    uv run python -m scripts.simulate_conversation \\
        simulations/scenarios/problem_help.yaml \\
        --verbose

Scenario ``user_id`` / ``doc_id`` override ``SIM_USER_ID`` / ``SIM_ACTIVE_DOC_ID``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from livekit import rtc
from livekit.agents import RoomInputOptions
from livekit.agents.testing import fake_job_context
from livekit.agents.voice.run_result import RunEvent

from app.agent.session_factory import build_session_bundle, send_initial_greeting
from app.agent.simulation import assert_turn_expectations, load_scenario
from app.config import Settings, get_settings


def _format_event(event: RunEvent) -> dict[str, object]:
    if event.type == "message":
        return {
            "type": "message",
            "role": event.item.role,
            "text": event.item.text_content,
        }
    if event.type == "function_call":
        return {
            "type": "function_call",
            "name": event.item.name,
            "arguments": event.item.arguments,
        }
    if event.type == "function_call_output":
        return {
            "type": "function_call_output",
            "name": event.item.name,
            "output": event.item.output,
            "is_error": event.item.is_error,
        }
    return {"type": event.type}


def _apply_board_text(session_data, text: str | None) -> None:
    if not text:
        return
    state = session_data.board_state
    state.user_text = text
    state.is_blank = False
    state.refreshed_at = time.time()


async def run_scenario(
    scenario_path: Path,
    *,
    settings: Settings,
    verbose: bool = False,
) -> None:
    scenario = load_scenario(scenario_path)
    user_id = scenario.user_id or settings.sim_user_id or None
    active_doc_id = scenario.doc_id or settings.sim_active_doc_id or None

    print(f"Scenario: {scenario.name}", flush=True)
    if user_id or active_doc_id:
        print(f"  identity: user_id={user_id!r} doc_id={active_doc_id!r}", flush=True)

    async with rtc.Room() as room:
        with fake_job_context(room=room):
            bundle = await build_session_bundle(
                room=room,
                settings=settings,
                user_id=user_id,
                active_doc_id=active_doc_id,
            )
            _apply_board_text(bundle.session_data, scenario.board_text)

            await bundle.session.start(
                agent=bundle.agent,
                room=room,
                room_input_options=RoomInputOptions(),
                record=False,
            )

            try:
                if scenario.greeting:
                    await send_initial_greeting(
                        bundle.session,
                        has_progress=bundle.session_data.progress_engine is not None,
                    )
                    if verbose:
                        print("--- greeting (see assistant reply in turn events) ---", flush=True)

                for index, turn in enumerate(scenario.turns, start=1):
                    label = f"turn {index}"
                    board_text = (
                        turn.board_text if turn.board_text is not None else scenario.board_text
                    )
                    _apply_board_text(bundle.session_data, board_text)

                    print(f"\n--- {label}: student ---", flush=True)
                    print(turn.student, flush=True)

                    run = bundle.session.run(user_input=turn.student)
                    await run

                    if verbose:
                        print(f"--- {label}: events ---", flush=True)
                        for event in run.events:
                            print(json.dumps(_format_event(event), ensure_ascii=False), flush=True)

                    assert_turn_expectations(run, turn.expect, turn_label=label)
                    print(f"  ✓ {label} expectations passed", flush=True)
            finally:
                await bundle.listener.aclose()
                await bundle.session.aclose()


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
        help="Print RunResult events after each turn",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
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
