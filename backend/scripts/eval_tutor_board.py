"""Evaluate tutor-board behavior against a golden case set.

Axes covered:

- ``usage`` — extractor emits (or withholds) tutor cards appropriately
- ``content`` — emitted card payloads contain the right math/visual detail
- ``card_kind`` — text/plot/diagram/shape choice matches the teaching moment
- ``grouping`` — same explanation line appends to an existing card; a new line creates a fresh card
- ``reference`` — tutor utterances reference (or avoid referencing) the board

Run from backend/::

    uv run python -m scripts.eval_tutor_board \\
        --golden evals/golden/tutor_board.jsonl

Reference-axis cases are scored statically from golden utterances.
Usage/content/card_kind cases call the configured board extractor
(``BOARD_EXTRACTOR=openai`` + ``OPENAI_API_KEY`` by default).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.evals.tutor_board import (
    evaluate_tutor_board_cases,
    load_tutor_board_cases,
    render_markdown_report,
    report_to_dict,
)
from app.agent.whiteboard.extractor.factory import get_board_extractor
from app.config import get_settings


async def _amain(args: argparse.Namespace) -> int:
    golden_path = Path(args.golden)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = load_tutor_board_cases(golden_path)
    if args.reference_only:
        cases = [case for case in cases if case.axis == "reference"]
        if not cases:
            raise SystemExit("No reference-axis cases found in golden set.")

    settings = get_settings()
    extractor = None
    if any(case.axis != "reference" for case in cases):
        if settings.board_extractor == "null":
            raise SystemExit(
                "BOARD_EXTRACTOR=null but golden set includes extractor cases. "
                "Set BOARD_EXTRACTOR=openai and OPENAI_API_KEY before running."
            )
        extractor = get_board_extractor()

    print(
        f"Evaluating tutor board ({len(cases)} cases) with "
        f"BOARD_EXTRACTOR={settings.board_extractor} "
        f"model={settings.board_extractor_model}",
        flush=True,
    )

    report = await evaluate_tutor_board_cases(cases, extractor=extractor)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"tutor_board_eval_{stamp}.json"
    md_path = output_dir / f"tutor_board_eval_{stamp}.md"

    payload = report_to_dict(
        report,
        golden_path=str(golden_path),
        created_at=stamp,
        descriptions={case.id: case.description for case in cases},
    )
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    md_path.write_text(render_markdown_report(report, golden_path=str(golden_path)))

    print(f"Overall pass rate: {report.pass_rate:.1%}")
    for summary in report.axis_summaries():
        print(f"  {summary.axis}: {summary.passed}/{summary.total} ({summary.pass_rate:.1%})")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    if args.frontend_output:
        frontend_path = Path(args.frontend_output)
        frontend_path.parent.mkdir(parents=True, exist_ok=True)
        frontend_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"Wrote {frontend_path}")

    return 0 if report.pass_rate == 1.0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        default="evals/golden/tutor_board.jsonl",
        help="Path to tutor board golden JSONL, relative to backend/ by default.",
    )
    parser.add_argument("--output-dir", default="evals/results")
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Score only reference-axis cases (no board extractor API calls).",
    )
    parser.add_argument(
        "--frontend-output",
        default="../frontend/src/data/tutorBoardEval.generated.json",
        help="Optional dashboard JSON path. Pass empty string to skip.",
    )
    args = parser.parse_args()
    if not args.frontend_output:
        args.frontend_output = None
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
