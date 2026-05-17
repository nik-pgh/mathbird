"""Diagnostic: dump distributions of block_type / exercise_number / etc. from Qdrant.

Run from the repo root or from backend/:

    uv run python -m scripts.inspect_qdrant
    uv run python -m scripts.inspect_qdrant --doc-id <doc_id>
    uv run python -m scripts.inspect_qdrant --sample 5

Reads QDRANT_URL / QDRANT_API_KEY / QDRANT_COLLECTION from Settings.
No vendor SDKs are imported outside this script — it's a one-off probe.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from typing import Any

from app.config import get_settings


def _decode_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the metadata dict out of a Qdrant point payload.

    LlamaIndex's QdrantVectorStore serializes the whole Node into
    ``_node_content``. Falls back to top-level payload keys for any rows
    written outside that path.
    """
    if payload.get("_node_content"):
        try:
            from llama_index.core.vector_stores.utils import metadata_dict_to_node

            node = metadata_dict_to_node(payload)
            return dict(node.metadata or {})
        except Exception:
            pass
    if isinstance(payload.get("metadata"), dict):
        return dict(payload["metadata"])
    return {k: v for k, v in payload.items() if k != "_node_content"}


def _decode_text(payload: dict[str, Any]) -> str:
    if payload.get("_node_content"):
        try:
            from llama_index.core.vector_stores.utils import metadata_dict_to_node

            return metadata_dict_to_node(payload).get_content()
        except Exception:
            pass
    return str(payload.get("text") or payload.get("document") or "")


async def _scroll_all(client: Any, collection: str, doc_id: str | None) -> list[Any]:
    from qdrant_client.http import models

    scroll_filter = None
    if doc_id:
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="textbook_doc_id",
                    match=models.MatchValue(value=doc_id),
                )
            ]
        )

    points: list[Any] = []
    offset: Any = None
    while True:
        result = await client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        batch, offset = result if isinstance(result, tuple) else (result, None)
        points.extend(batch)
        if not offset or not batch:
            break
    return points


def _truncate(text: str, n: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _print_distribution(label: str, counter: Counter[Any], *, top: int = 20) -> None:
    print(f"\n{label} (total values: {sum(counter.values())}, distinct: {len(counter)})")
    if not counter:
        print("  (empty)")
        return
    for value, count in counter.most_common(top):
        rendered = repr(value) if value == "" else value
        print(f"  {rendered}: {count}")
    if len(counter) > top:
        rest = sum(c for _, c in counter.most_common()[top:])
        print(f"  … {len(counter) - top} more values ({rest} points)")


async def _amain(args: argparse.Namespace) -> None:
    settings = get_settings()
    print(f"Qdrant: {settings.qdrant_url}  collection={settings.qdrant_collection}")
    if args.doc_id:
        print(f"Filtering by textbook_doc_id={args.doc_id}")

    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    try:
        points = await _scroll_all(client, settings.qdrant_collection, args.doc_id)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            res = close()
            if hasattr(res, "__await__"):
                await res

    print(f"\nTotal points: {len(points)}")
    if not points:
        print("Collection is empty (or filter excluded everything).")
        return

    block_types: Counter[str] = Counter()
    exercise_numbers: Counter[str] = Counter()
    example_numbers: Counter[str] = Counter()
    doc_ids: Counter[str] = Counter()
    pages: Counter[int] = Counter()

    empty_exercise_samples: list[tuple[dict[str, Any], str]] = []
    has_exercise_samples: list[tuple[dict[str, Any], str]] = []
    looks_like_problem_but_unnumbered: list[tuple[dict[str, Any], str]] = []

    # Heuristic to spot indexing misses: text that *looks* like a problem
    # statement but has no exercise_number metadata.
    import re

    looks_like_problem = re.compile(
        r"\b(problem|exercise|question)\s+\d+\b|^\s*\d+\s*[.)]\s+\S",
        re.IGNORECASE | re.MULTILINE,
    )

    for point in points:
        payload = getattr(point, "payload", None) or {}
        metadata = _decode_metadata(payload)
        text = _decode_text(payload)

        block_types[str(metadata.get("block_type", "unknown"))] += 1
        exercise_numbers[str(metadata.get("exercise_number", ""))] += 1
        example_numbers[str(metadata.get("example_number", ""))] += 1
        doc_ids[str(metadata.get("textbook_doc_id") or metadata.get("doc_id", ""))] += 1
        try:
            pages[int(metadata.get("page_number", 0) or 0)] += 1
        except (TypeError, ValueError):
            pages[0] += 1

        exercise_value = str(metadata.get("exercise_number", ""))
        if exercise_value and len(has_exercise_samples) < args.sample:
            has_exercise_samples.append((metadata, text))
        if not exercise_value:
            if len(empty_exercise_samples) < args.sample:
                empty_exercise_samples.append((metadata, text))
            if looks_like_problem.search(text) and len(
                looks_like_problem_but_unnumbered
            ) < args.sample:
                looks_like_problem_but_unnumbered.append((metadata, text))

    _print_distribution("block_type", block_types)
    _print_distribution("exercise_number", exercise_numbers)
    _print_distribution("example_number", example_numbers)
    _print_distribution("textbook_doc_id", doc_ids)
    page_lo = min(pages) if pages else "-"
    page_hi = max(pages) if pages else "-"
    print(f"\npages: {page_lo}..{page_hi} ({len(pages)} distinct)")

    def _dump(label: str, samples: list[tuple[dict[str, Any], str]]) -> None:
        print(f"\n--- {label} (showing up to {args.sample}) ---")
        if not samples:
            print("  (none)")
            return
        for metadata, text in samples:
            print(
                f"  page={metadata.get('page_number', '?')} "
                f"block_type={metadata.get('block_type', '?')} "
                f"ex#={metadata.get('exercise_number', '') or '-'} "
                f"ex_ex#={metadata.get('example_number', '') or '-'}"
            )
            print(f"    text: {_truncate(text)}")

    _dump("Samples WITH exercise_number set", has_exercise_samples)
    _dump("Samples with NO exercise_number", empty_exercise_samples)
    _dump(
        "SUSPECTED INDEXING MISSES (text looks like a problem but exercise_number is empty)",
        looks_like_problem_but_unnumbered,
    )

    empty = exercise_numbers.get("", 0)
    nonempty = sum(c for k, c in exercise_numbers.items() if k)
    print(
        f"\nSummary: {nonempty} points have a non-empty exercise_number, "
        f"{empty} are empty. Suspected misses above show empty rows whose text "
        f"reads like a problem statement — those would not be reachable via "
        f"structured_lookup(exercise_number=...)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Only inspect points for this textbook_doc_id (default: all docs).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="How many sample rows to print per section (default: 5).",
    )
    args = parser.parse_args()
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
