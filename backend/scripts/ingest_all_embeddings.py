"""Ingest one PDF into every embedding collection (parse once).

LlamaParse runs a single time; each provider/model pair gets its own Qdrant
collection via ``QDRANT_COLLECTION=auto``.

Run from ``backend/``::

    uv run python -m scripts.ingest_all_embeddings \\
        ../materials/deep_learning_ian_goodfellow_chapter_2.pdf \\
        --doc-id goodfellow-ch2

    # Subset of models only
    uv run python -m scripts.ingest_all_embeddings book.pdf \\
        --target openai:text-embedding-3-small \\
        --target google:gemini-embedding-001

    # Avoid parallel embedding API calls (slower, gentler on rate limits)
    uv run python -m scripts.ingest_all_embeddings book.pdf --sequential
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import EmbeddingProvider, get_settings
from app.rag.embeddings import embedding_collection_name
from app.rag.multi_ingest import (
    DEFAULT_EMBEDDING_TARGETS,
    MultiIngestEvent,
    ingest_pdf_all_embeddings,
)


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}m {remainder:.0f}s"


def _print_progress(event: MultiIngestEvent) -> None:
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    if event.kind == "parse_start":
        print(f"{stamp}  parse  start", flush=True)
        return
    if event.kind == "parse_done":
        elapsed = _format_elapsed(event.elapsed_seconds)
        print(f"{stamp}  parse  done   {event.node_count} nodes ({elapsed})", flush=True)
        return
    if event.kind == "embed_start":
        label = f"{event.provider}/{event.model}"
        print(
            f"{stamp}  embed  start  [{event.target_index}/{event.target_total}] "
            f"{label} -> {event.collection_name}",
            flush=True,
        )
        return
    if event.kind == "embed_done":
        label = f"{event.provider}/{event.model}"
        print(
            f"{stamp}  embed  done   [{event.target_index}/{event.target_total}] "
            f"{label}  {event.node_count} nodes ({_format_elapsed(event.elapsed_seconds)})",
            flush=True,
        )
        return
    if event.kind == "embed_failed":
        label = f"{event.provider}/{event.model}"
        print(
            f"{stamp}  embed  FAIL   [{event.target_index}/{event.target_total}] "
            f"{label} ({_format_elapsed(event.elapsed_seconds)})",
            file=sys.stderr,
            flush=True,
        )
        print(f"           {event.error}", file=sys.stderr, flush=True)
        return
    if event.kind == "all_done":
        print(f"{stamp}  done", flush=True)


def _parse_target(raw: str) -> tuple[EmbeddingProvider, str]:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(
            f"Expected provider:model, got {raw!r}. "
            "Example: openai:text-embedding-3-small"
        )
    provider, model = raw.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise argparse.ArgumentTypeError(f"Invalid target {raw!r}")
    return provider, model  # type: ignore[return-value]


def _default_doc_id(path: Path) -> str:
    slug = path.stem.lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in slug).strip("-")
    return cleaned or "document"


def _resolve_targets(
    explicit: list[tuple[EmbeddingProvider, str]] | None,
    *,
    skip_providers: set[str],
) -> tuple[tuple[EmbeddingProvider, str], ...]:
    targets = tuple(explicit) if explicit else DEFAULT_EMBEDDING_TARGETS
    if not skip_providers:
        return targets
    return tuple(t for t in targets if t[0] not in skip_providers)


async def _amain(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    doc_id = args.doc_id or _default_doc_id(pdf_path)
    skip_providers = set(args.skip_provider or [])
    targets = _resolve_targets(args.target, skip_providers=skip_providers)
    if not targets:
        print("No embedding targets left after filtering.", file=sys.stderr)
        return 1

    settings = get_settings()

    print(f"PDF: {pdf_path}")
    print(f"doc_id: {doc_id}")
    print(f"Qdrant: {settings.qdrant_url}")
    print(f"Targets ({len(targets)}):")
    for provider, model in targets:
        print(f"  {provider}:{model} -> {embedding_collection_name(provider, model)}")
    if skip_providers:
        print(f"Skipped providers: {', '.join(sorted(skip_providers))}")
    print(f"Mode: {'parallel' if args.parallel else 'sequential'}")
    if args.continue_on_error:
        print("Errors: continue (partial success allowed)")
    print()

    report = await ingest_pdf_all_embeddings(
        str(pdf_path),
        doc_id=doc_id,
        targets=targets,
        parallel=args.parallel,
        continue_on_error=args.continue_on_error,
        on_progress=None if args.quiet else _print_progress,
    )

    if not args.quiet and (report.successes or report.failures):
        print()
    if report.successes:
        print("Succeeded:")
        for result in report.successes:
            print(
                f"  {result.embedding_provider}/{result.embedding_model} "
                f"-> {result.collection_name} ({result.node_count} nodes)"
            )

    if report.failures:
        print("\nFailed:", file=sys.stderr)
        for failure in report.failures:
            print(
                f"  {failure.embedding_provider}/{failure.embedding_model} "
                f"-> {failure.collection_name}",
                file=sys.stderr,
            )
            print(f"    {failure.error}", file=sys.stderr)

    if report.ok:
        return 0

    print(
        "\nTip: Use --sequential or --continue-on-error if one provider is rate-limited.",
        file=sys.stderr,
    )
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Path to the PDF file to ingest.")
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Stable document id stored in Qdrant metadata (default: slug from filename).",
    )
    parser.add_argument(
        "--target",
        action="append",
        type=_parse_target,
        metavar="PROVIDER:MODEL",
        help=(
            "Embedding pair to index (repeatable). "
            "Default: OpenAI small/large, Cohere English/v4, Google Gemini, and Mistral."
        ),
    )
    parser.add_argument(
        "--skip-provider",
        action="append",
        metavar="PROVIDER",
        help="Omit all targets for this provider (repeatable), e.g. voyage.",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Insert into collections one at a time instead of in parallel.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep going when one embedding provider fails; report all outcomes.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress live progress lines (summary only).",
    )
    args = parser.parse_args()
    args.parallel = not args.sequential
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
