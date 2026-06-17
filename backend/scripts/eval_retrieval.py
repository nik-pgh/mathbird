"""Evaluate retrieval quality across embedding collections.

Run from backend/::

    uv run python -m scripts.eval_retrieval \\
        --golden evals/golden/goodfellow_ch2_retrieval.jsonl \\
        --top-k 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import EmbeddingProvider, get_settings
from app.rag.evaluation import (
    TargetFailure,
    evaluate_target,
    failure_to_dict,
    load_golden_cases,
    render_markdown_report,
    report_to_dict,
)
from app.rag.multi_ingest import DEFAULT_EMBEDDING_TARGETS


def _parse_target(raw: str) -> tuple[EmbeddingProvider, str]:
    if ":" not in raw:
        raise argparse.ArgumentTypeError("Expected provider:model")
    provider, model = raw.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise argparse.ArgumentTypeError(f"Invalid target {raw!r}")
    return provider, model  # type: ignore[return-value]


async def _amain(args: argparse.Namespace) -> int:
    if args.top_k < 5:
        raise ValueError("top_k must be at least 5")

    golden_path = Path(args.golden)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_golden_cases(golden_path)
    settings = get_settings()
    targets = tuple(args.target or DEFAULT_EMBEDDING_TARGETS)

    reports = []
    failures = []
    for index, (provider, model) in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] {provider}/{model}", flush=True)
        try:
            reports.append(
                await evaluate_target(
                    cases,
                    base_settings=settings,
                    provider=provider,
                    model=model,
                    top_k=args.top_k,
                )
            )
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            print(f"FAIL {provider}/{model}: {error}", flush=True)
            failures.append(
                TargetFailure(
                    provider=provider,
                    model=model,
                    error=error,
                )
            )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"retrieval_eval_{stamp}.json"
    md_path = output_dir / f"retrieval_eval_{stamp}.md"

    payload = {
        "schema_version": 2,
        "comparison_axis": "embedding_model",
        "created_at": stamp,
        "golden_path": str(golden_path),
        "top_k": args.top_k,
        "targets": [report_to_dict(report, cases=cases) for report in reports],
        "failures": [failure_to_dict(failure) for failure in failures],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    md_path.write_text(
        render_markdown_report(
            reports,
            failures=failures,
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
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        default="evals/golden/goodfellow_ch2_retrieval.jsonl",
        help="Path to golden JSONL, relative to backend/ by default.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", default="evals/results")
    parser.add_argument(
        "--target",
        action="append",
        type=_parse_target,
        metavar="PROVIDER:MODEL",
        help="Evaluate one embedding target; repeat to compare a subset.",
    )
    parser.add_argument(
        "--frontend-output",
        help=(
            "Optional path for the dashboard JSON, e.g. "
            "../frontend/src/data/retrievalEval.generated.json."
        ),
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
