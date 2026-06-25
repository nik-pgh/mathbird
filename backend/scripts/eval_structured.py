"""Evaluate structured lookup coverage against a golden query set.

Run from backend/::

    uv run python -m scripts.eval_structured \\
        --golden evals/golden/goodfellow_ch2_structured.jsonl \\
        --top-k 5 \\
        --frontend-output ../frontend/src/data/structuredEval.generated.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.rag.evaluation import (
    evaluate_structured_paths,
    load_structured_golden_cases,
    render_markdown_report,
    report_to_dict,
    structured_case_to_golden,
    structured_report_to_dict,
)


async def _amain(args: argparse.Namespace) -> int:
    if args.top_k < 5:
        raise ValueError("top_k must be at least 5")

    golden_path = Path(args.golden)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_structured_golden_cases(golden_path)
    settings = get_settings()

    print(
        f"Evaluating structured lookup on {settings.embedding_provider}/"
        f"{settings.embedding_model} ({settings.resolved_qdrant_collection})",
        flush=True,
    )
    reports = await evaluate_structured_paths(
        cases,
        base_settings=settings,
        top_k=args.top_k,
    )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"structured_eval_{stamp}.json"
    md_path = output_dir / f"structured_eval_{stamp}.md"

    golden_cases = [structured_case_to_golden(case) for case in cases]
    payload = {
        "schema_version": 2,
        "comparison_axis": "structured_lookup",
        "created_at": stamp,
        "golden_path": str(golden_path),
        "top_k": args.top_k,
        "targets": [
            structured_report_to_dict(reports[0], cases=cases),
            report_to_dict(reports[1], cases=golden_cases),
            report_to_dict(reports[2], cases=golden_cases),
        ],
        "failures": [],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    md_path.write_text(
        render_markdown_report(
            reports,
            golden_path=str(golden_path),
            top_k=args.top_k,
        )
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if args.frontend_output:
        frontend_path = Path(args.frontend_output)
        frontend_path.parent.mkdir(parents=True, exist_ok=True)
        frontend_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"Wrote {frontend_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        default="evals/golden/goodfellow_ch2_structured.jsonl",
        help="Path to structured golden JSONL, relative to backend/ by default.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", default="evals/results")
    parser.add_argument(
        "--frontend-output",
        help=(
            "Optional path for the dashboard JSON, e.g. "
            "../frontend/src/data/structuredEval.generated.json."
        ),
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
