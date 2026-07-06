"""Evaluate structured lookup coverage against a golden query set.

Run from backend/::

    uv run python -m scripts.eval_structured \\
        --golden evals/golden/goodfellow_ch2_structured.jsonl \\
        --top-k 5

Writes ``structuredEval.{policy}[.{variant}].generated.json`` under
``--frontend-data-dir`` (one file per Qdrant collection snapshot).
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
from app.rag.structured_eval_output import (
    extract_chunk_policy_from_collection,
    structured_eval_frontend_path,
)


def resolve_frontend_output_path(
    *,
    collection_name: str,
    frontend_data_dir: Path | None,
) -> Path | None:
    if frontend_data_dir is None:
        return None
    chunk_policy = extract_chunk_policy_from_collection(collection_name)
    if not chunk_policy:
        raise ValueError(
            f"Cannot derive chunk policy from collection {collection_name!r}. "
            "Expected a mathbird_chunk_<policy>_<provider>_<model> collection name."
        )
    return structured_eval_frontend_path(frontend_data_dir, chunk_policy, collection_name=collection_name)


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
    frontend_path = resolve_frontend_output_path(
        collection_name=settings.resolved_qdrant_collection,
        frontend_data_dir=Path(args.frontend_data_dir) if args.frontend_data_dir else None,
    )
    if frontend_path is not None:
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
        "--frontend-data-dir",
        default="../frontend/src/data",
        help=(
            "Directory for dashboard JSON. Writes structuredEval.{policy}[.{variant}].generated.json "
            "derived from the active Qdrant collection name."
        ),
    )
    parser.add_argument(
        "--no-frontend-output",
        action="store_true",
        help="Skip writing dashboard JSON under --frontend-data-dir.",
    )
    args = parser.parse_args()
    if args.no_frontend_output:
        args.frontend_data_dir = None
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
