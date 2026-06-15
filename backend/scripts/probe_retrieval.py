"""End-to-end retrieval probe.

Reproduces what ``search_documents`` would do for a given query and shows
exactly where it falls down. Three pieces:

1. Dumps the raw top-level Qdrant payload for one stored point so we can see
   whether ``exercise_number`` actually lives at the top level (where the
   ``MatchValue`` filter looks) or only inside the serialized
   ``_node_content``.
2. Prints what ``parse_retrieval_query`` extracts for the probe query.
3. Runs the full retriever pipeline against Qdrant and prints what it
   returns — first the structured branch alone, then the semantic branch
   alone, then the public ``retrieve()`` which picks one.

Run::

    cd backend
    uv run python -m scripts.probe_retrieval "tell me about problem 2"
    uv run python -m scripts.probe_retrieval --doc-id <doc_id> "problem 2"
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.config import get_settings
from app.rag.parsing import RetrievalRequest
from app.rag.query_parser import parse_retrieval_query


def _truncate(text: str, n: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


async def _dump_raw_payload(client: Any, collection: str) -> None:
    """Print one full Qdrant payload so we can see top-level vs nested keys."""
    result = await client.scroll(
        collection_name=collection,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    points, _ = result if isinstance(result, tuple) else (result, None)
    if not points:
        print("  (no points)")
        return

    payload = dict(getattr(points[0], "payload", {}) or {})
    node_content = payload.pop("_node_content", None)
    print("Top-level payload keys:")
    for key in sorted(payload.keys()):
        value = payload[key]
        rendered = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        print(f"  {key} ({type(value).__name__}): {_truncate(rendered, 100)}")
    print(f"\n_node_content present: {node_content is not None}")
    if node_content:
        print("  (this is the serialized node JSON; metadata lives inside)")


async def _raw_filter_count(
    client: Any, collection: str, exercise_number: str, doc_id: str | None
) -> int:
    """Run the exact same Qdrant filter structured_lookup uses, return the count."""
    from qdrant_client.http import models

    must: list[Any] = [
        models.FieldCondition(
            key="exercise_number",
            match=models.MatchValue(value=exercise_number),
        )
    ]
    if doc_id:
        must.append(
            models.FieldCondition(
                key="textbook_doc_id",
                match=models.MatchValue(value=doc_id),
            )
        )
    result = await client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(must=must),
        limit=20,
        with_payload=True,
        with_vectors=False,
    )
    points, _ = result if isinstance(result, tuple) else (result, None)
    return len(points)


async def _run_retriever(query: str, doc_id: str | None) -> None:
    """Call the actual retriever the same way ``search_documents`` does."""
    from app.rag.formatter import format_records_as_chunks
    from app.rag.retriever import get_retriever

    retriever = get_retriever()
    parsed = parse_retrieval_query(query)
    print("\nparse_retrieval_query():")
    print(f"  page_number={parsed.page_number}")
    print(f"  chapter_number={parsed.chapter_number!r}")
    print(f"  exercise_number={parsed.exercise_number!r}")
    print(f"  example_number={parsed.example_number!r}")
    print(f"  is_structured_lookup={parsed.is_structured_lookup}")

    doc_ids = (doc_id,) if doc_id else ()
    settings = get_settings()
    request = RetrievalRequest(
        query=query,
        top_k=settings.rag_top_k,
        doc_ids=doc_ids,
        page_number=parsed.page_number,
        chapter_number=parsed.chapter_number,
        exercise_number=parsed.exercise_number,
        example_number=parsed.example_number,
    )

    store = getattr(retriever, "store", None)
    if store is None or not parsed.is_structured_lookup:
        print("\nSkipping structured-only probe (no store / not structured).")
    else:
        print("\n[structured_lookup only]")
        records = await store.structured_lookup(request)
        print(f"  returned {len(records)} record(s)")
        for rec in records[:5]:
            print(
                f"    page={rec.page_number} block={rec.block_type} ex#={rec.exercise_number!r}"
            )
            print(f"      text: {_truncate(rec.text)}")
        chunks = format_records_as_chunks(records)
        print(f"  format_records_as_chunks() → {len(chunks)} chunk(s)")

    print("\n[semantic_search only]")
    if store is None:
        print("  (retriever has no .store — skipping)")
    else:
        records = await store.semantic_search(request)
        print(f"  returned {len(records)} record(s)")
        for rec in records[:5]:
            print(
                f"    page={rec.page_number} block={rec.block_type} "
                f"score={rec.score} ex#={rec.exercise_number!r}"
            )
            print(f"      text: {_truncate(rec.text)}")

    print("\n[public retriever.retrieve() — what search_documents actually sees]")
    chunks = await retriever.retrieve(query, top_k=settings.rag_top_k, doc_ids=doc_ids)
    print(f"  returned {len(chunks)} chunk(s)")
    for chunk in chunks[:5]:
        print(f"    source={chunk.source} score={chunk.score}")
        print(f"      text: {_truncate(chunk.text)}")


async def _amain(args: argparse.Namespace) -> None:
    settings = get_settings()
    print(f"Qdrant: {settings.qdrant_url}  collection={settings.resolved_qdrant_collection}")
    print(f"Query: {args.query!r}")
    if args.doc_id:
        print(f"doc_id filter: {args.doc_id}")

    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    try:
        print("\n=== 1. Raw payload of one stored point ===")
        await _dump_raw_payload(client, settings.resolved_qdrant_collection)

        parsed = parse_retrieval_query(args.query)
        if parsed.exercise_number:
            print(
                f"\n=== 2. Raw Qdrant filter: exercise_number == "
                f"{parsed.exercise_number!r} ==="
            )
            hits = await _raw_filter_count(
                client, settings.resolved_qdrant_collection, parsed.exercise_number, args.doc_id
            )
            print(f"  matching points: {hits}")
            if hits == 0:
                print(
                    "  ⚠ This is the smoking gun: the field/value doesn't match "
                    "anything at top-level payload."
                )
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            res = close()
            if hasattr(res, "__await__"):
                await res

    print("\n=== 3. Full retriever pipeline ===")
    await _run_retriever(args.query, args.doc_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="The query to probe, e.g. 'tell me about problem 2'.")
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Optional textbook_doc_id to filter retrieval to one document.",
    )
    args = parser.parse_args()
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
