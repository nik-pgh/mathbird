"""Evaluate retrieval quality across chunking policies.

Run from backend/::

    uv run python -m scripts.eval_chunking \\
        --pdf materials/deep_learning_ian_goodfellow_chapter_2.pdf \\
        --doc-id goodfellow-ch2 \\
        --golden evals/golden/goodfellow_ch2_retrieval.jsonl \\
        --provider cohere \\
        --model embed-v4.0 \\
        --frontend-output ../frontend/src/data/retrievalEval.generated.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.config import EmbeddingProvider, get_settings
from app.rag.embeddings import embedding_collection_name
from app.rag.evaluation import (
    TargetFailure,
    evaluate_target,
    failure_to_dict,
    load_golden_cases,
    render_markdown_report,
    report_to_dict,
)
from app.rag.indexing import DEFAULT_CHUNK_POLICIES, ChunkPolicy, get_chunk_policy
from app.rag.llamaindex_qdrant import build_qdrant_index_stack, close_qdrant_client
from app.rag.multi_ingest import build_parser


def chunk_collection_name(policy: ChunkPolicy, provider: str, model: str) -> str:
    return embedding_collection_name(provider, model, prefix=f"mathbird_chunk_{policy.name}")


def _parse_provider(raw: str) -> EmbeddingProvider:
    value = raw.strip()
    if not value:
        raise argparse.ArgumentTypeError("Provider cannot be empty")
    return value  # type: ignore[return-value]


async def _parse_once(pdf_path: str, *, doc_id: str):
    settings = get_settings()
    parser = build_parser(settings)
    return await parser.parse_pdf(pdf_path, doc_id=doc_id, filename=Path(pdf_path).name)


async def _index_policy(
    *,
    document,
    policy: ChunkPolicy,
    provider: EmbeddingProvider,
    model: str,
) -> tuple[str, int]:
    from app.rag.indexing import parsed_document_to_chunked_nodes

    settings = get_settings().model_copy(
        update={
            "embedding_provider": provider,
            "embedding_model": model,
            "qdrant_collection": chunk_collection_name(policy, provider, model),
        }
    )
    stack = build_qdrant_index_stack(settings)
    try:
        nodes = parsed_document_to_chunked_nodes(document, policy_name=policy.name)
        if nodes:
            await stack.index.ainsert_nodes(nodes)
            await stack.store.ensure_payload_indexes()
        return stack.collection_name, len(nodes)
    finally:
        await close_qdrant_client(stack.qdrant_client)


async def evaluate_chunk_policies(
    *,
    pdf_path: str,
    doc_id: str,
    golden_path: str,
    provider: EmbeddingProvider,
    model: str,
    top_k: int,
    policies: Sequence[ChunkPolicy],
) -> tuple[list, list[TargetFailure]]:
    document = await _parse_once(pdf_path, doc_id=doc_id)
    cases = load_golden_cases(golden_path)
    base_settings = get_settings()
    reports = []
    failures: list[TargetFailure] = []

    for index, policy in enumerate(policies, start=1):
        print(f"[{index}/{len(policies)}] chunk policy {policy.name}", flush=True)
        try:
            collection_name, node_count = await _index_policy(
                document=document,
                policy=policy,
                provider=provider,
                model=model,
            )
            reports.append(
                await evaluate_target(
                    cases,
                    base_settings=base_settings,
                    provider=provider,
                    model=model,
                    top_k=top_k,
                    collection_name=collection_name,
                    target_id=f"chunk:{policy.name}",
                    label=policy.label,
                    comparison_axis="chunk_policy",
                    metadata={
                        "chunk_policy": policy.name,
                        "chunk_policy_label": policy.label,
                        "chunk_policy_description": policy.description,
                        "embedding_provider": provider,
                        "embedding_model": model,
                        "node_count": node_count,
                    },
                )
            )
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            print(f"FAIL {policy.name}: {error}", flush=True)
            failures.append(
                TargetFailure(
                    provider=provider,
                    model=model,
                    error=error,
                    target_id=f"chunk:{policy.name}",
                    label=policy.label,
                    comparison_axis="chunk_policy",
                    metadata={"chunk_policy": policy.name},
                )
            )

    return reports, failures


def _write_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


async def _amain(args: argparse.Namespace) -> int:
    if args.top_k < 5:
        raise ValueError("top_k must be at least 5")

    policies = tuple(get_chunk_policy(name) for name in (args.policy or ()))
    if not policies:
        policies = DEFAULT_CHUNK_POLICIES

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports, failures = await evaluate_chunk_policies(
        pdf_path=args.pdf,
        doc_id=args.doc_id,
        golden_path=args.golden,
        provider=args.provider,
        model=args.model,
        top_k=args.top_k,
        policies=policies,
    )

    cases = load_golden_cases(args.golden)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "schema_version": 2,
        "comparison_axis": "chunk_policy",
        "created_at": stamp,
        "golden_path": args.golden,
        "top_k": args.top_k,
        "targets": [report_to_dict(report, cases=cases) for report in reports],
        "failures": [failure_to_dict(failure) for failure in failures],
    }

    json_path = output_dir / f"chunking_eval_{stamp}.json"
    md_path = output_dir / f"chunking_eval_{stamp}.md"
    _write_payload(json_path, payload)
    md_path.write_text(
        render_markdown_report(
            reports,
            failures=failures,
            golden_path=args.golden,
            top_k=args.top_k,
        )
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    if args.frontend_output:
        frontend_path = Path(args.frontend_output)
        _write_payload(frontend_path, payload)
        print(f"Wrote {frontend_path}")

    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf", required=True, help="PDF to parse and index for each chunk policy."
    )
    parser.add_argument("--doc-id", required=True, help="Document id used by the golden cases.")
    parser.add_argument(
        "--golden",
        default="evals/golden/goodfellow_ch2_retrieval.jsonl",
        help="Path to golden JSONL, relative to backend/ by default.",
    )
    parser.add_argument("--provider", type=_parse_provider, default="cohere")
    parser.add_argument("--model", default="embed-v4.0")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", default="evals/results")
    parser.add_argument(
        "--policy",
        action="append",
        help="Chunk policy to evaluate; repeat to compare a subset. Defaults to all built-ins.",
    )
    parser.add_argument(
        "--frontend-output",
        help=(
            "Optional path for the dashboard JSON, e.g. "
            "../frontend/src/data/retrievalEval.generated.json."
        ),
    )
    raise SystemExit(asyncio.run(_amain(parser.parse_args())))


if __name__ == "__main__":
    main()
