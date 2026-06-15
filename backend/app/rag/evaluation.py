"""Retrieval evaluation utilities for golden textbook query sets."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from app.config import EmbeddingProvider, Settings
from app.rag.llamaindex_qdrant import (
    LlamaIndexQdrantRetriever,
    build_qdrant_index_stack,
    close_qdrant_client,
)
from app.rag.retriever import RetrievedChunk


@dataclass(frozen=True)
class GoldenCase:
    id: str
    doc_id: str
    query: str
    query_type: str
    expected_pages: tuple[int, ...]
    expected_printed_pages: tuple[int, ...]
    expected_section_titles: tuple[str, ...]
    expected_block_types: tuple[str, ...]
    must_contain: tuple[str, ...]
    golden_answer: str


def _tuple_str(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"Expected list, got {type(value).__name__}")
    return tuple(str(item) for item in value)


def _tuple_int(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"Expected list, got {type(value).__name__}")
    return tuple(int(item) for item in value)


def _case_from_row(row: dict[str, Any], *, line_number: int) -> GoldenCase:
    case_id = str(row.get("id") or "").strip()
    if not case_id:
        raise ValueError(f"Line {line_number}: missing id")

    expected = row.get("expected")
    if not isinstance(expected, dict):
        raise ValueError(f"{case_id}: expected must be an object")

    golden_answer = str(row.get("golden_answer") or "").strip()
    if not golden_answer:
        raise ValueError(f"{case_id}: golden_answer is required")

    pages = _tuple_int(expected.get("pages"))
    if not pages:
        raise ValueError(f"{case_id}: expected.pages is required")
    doc_id = str(row.get("doc_id") or "").strip()
    if not doc_id:
        raise ValueError(f"{case_id}: doc_id is required")
    query = str(row.get("query") or "").strip()
    if not query:
        raise ValueError(f"{case_id}: query is required")

    return GoldenCase(
        id=case_id,
        doc_id=doc_id,
        query=query,
        query_type=str(row.get("query_type") or "unknown").strip() or "unknown",
        expected_pages=pages,
        expected_printed_pages=_tuple_int(expected.get("printed_pages")),
        expected_section_titles=_tuple_str(expected.get("section_titles")),
        expected_block_types=_tuple_str(expected.get("block_types")),
        must_contain=_tuple_str(expected.get("must_contain")),
        golden_answer=golden_answer,
    )


def load_golden_cases(path: str | Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    seen: set[str] = set()
    source = Path(path)

    for line_number, line in enumerate(source.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {line_number}: expected JSON object")
        case = _case_from_row(row, line_number=line_number)
        if case.id in seen:
            raise ValueError(f"Duplicate golden case id: {case.id}")
        seen.add(case.id)
        cases.append(case)

    if not cases:
        raise ValueError(f"No golden cases found in {source}")
    return cases


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    query_type: str
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float
    best_rank: int | None
    best_score: float | None
    content_match_ratio: float
    matched_terms: tuple[str, ...]
    returned_sources: tuple[str, ...]


def _source_has_page(source: str, pages: tuple[int, ...]) -> bool:
    return any(re.search(rf"\bpage\s*=?\s*{page}\b", source, re.I) for page in pages)


def _matched_terms(texts: list[str], terms: tuple[str, ...]) -> tuple[str, ...]:
    haystack = "\n".join(texts).lower()
    return tuple(term for term in terms if term.lower() in haystack)


def _chunk_matches(case: GoldenCase, chunk: RetrievedChunk) -> bool:
    page_match = _source_has_page(chunk.source, case.expected_pages)
    if case.must_contain:
        chunk_text = chunk.text.lower()
        return page_match and any(term.lower() in chunk_text for term in case.must_contain)
    return page_match


def score_case(case: GoldenCase, chunks: list[RetrievedChunk]) -> CaseScore:
    best_rank: int | None = None
    best_score: float | None = None
    for index, chunk in enumerate(chunks, start=1):
        if _chunk_matches(case, chunk):
            best_rank = index
            best_score = chunk.score
            break

    matched = _matched_terms([chunk.text for chunk in chunks], case.must_contain)
    ratio = len(matched) / len(case.must_contain) if case.must_contain else 0.0

    return CaseScore(
        case_id=case.id,
        query_type=case.query_type,
        hit_at_1=best_rank == 1,
        hit_at_3=best_rank is not None and best_rank <= 3,
        hit_at_5=best_rank is not None and best_rank <= 5,
        reciprocal_rank=0.0 if best_rank is None else 1.0 / best_rank,
        best_rank=best_rank,
        best_score=best_score,
        content_match_ratio=ratio,
        matched_terms=matched,
        returned_sources=tuple(chunk.source for chunk in chunks),
    )


@dataclass(frozen=True)
class TargetReport:
    provider: str
    model: str
    collection_name: str
    case_count: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    avg_content_match: float
    avg_latency_ms: float
    scores: tuple[CaseScore, ...]


@dataclass(frozen=True)
class TargetFailure:
    provider: str
    model: str
    error: str


def _mean(values: tuple[float, ...]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate_scores(
    *,
    provider: str,
    model: str,
    collection_name: str,
    scores: list[CaseScore],
    latency_ms: tuple[float, ...],
) -> TargetReport:
    return TargetReport(
        provider=provider,
        model=model,
        collection_name=collection_name,
        case_count=len(scores),
        hit_at_1=_mean(tuple(1.0 if score.hit_at_1 else 0.0 for score in scores)),
        hit_at_3=_mean(tuple(1.0 if score.hit_at_3 else 0.0 for score in scores)),
        hit_at_5=_mean(tuple(1.0 if score.hit_at_5 else 0.0 for score in scores)),
        mrr=_mean(tuple(score.reciprocal_rank for score in scores)),
        avg_content_match=_mean(tuple(score.content_match_ratio for score in scores)),
        avg_latency_ms=_mean(latency_ms),
        scores=tuple(scores),
    )


async def evaluate_target(
    cases: list[GoldenCase],
    *,
    base_settings: Settings,
    provider: EmbeddingProvider,
    model: str,
    top_k: int,
) -> TargetReport:
    target_settings = base_settings.model_copy(
        update={
            "rag_provider": "llamaindex_qdrant",
            "qdrant_collection": "auto",
            "embedding_provider": provider,
            "embedding_model": model,
        }
    )
    stack = build_qdrant_index_stack(target_settings)
    retriever = LlamaIndexQdrantRetriever(
        parser=None,  # type: ignore[arg-type]
        index=stack.index,
        store=stack.store,
    )
    scores: list[CaseScore] = []
    latencies: list[float] = []
    try:
        for case in cases:
            started = time.perf_counter()
            chunks = await retriever.retrieve(case.query, top_k=top_k, doc_ids=(case.doc_id,))
            latencies.append((time.perf_counter() - started) * 1000)
            scores.append(score_case(case, chunks))
        return aggregate_scores(
            provider=provider,
            model=model,
            collection_name=stack.collection_name,
            scores=scores,
            latency_ms=tuple(latencies),
        )
    finally:
        await close_qdrant_client(stack.qdrant_client)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _markdown_table_cell(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    escaped = escape(normalized, quote=False).replace("|", "\\|")
    return escaped.replace("\n", "<br>")


def render_markdown_report(
    reports: list[TargetReport],
    *,
    failures: list[TargetFailure] | None = None,
    golden_path: str,
    top_k: int,
) -> str:
    ranked = sorted(
        reports,
        key=lambda report: (
            report.hit_at_3,
            report.mrr,
            report.hit_at_5,
            -report.avg_latency_ms,
        ),
        reverse=True,
    )
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Golden set: `{golden_path}`",
        f"- Top K: `{top_k}`",
        "",
        "| Provider | Model | Collection | Hit@1 | Hit@3 | Hit@5 | MRR | Content | Latency |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for report in ranked:
        lines.append(
            "| "
            f"{report.provider} | "
            f"{report.model} | "
            f"{report.collection_name} | "
            f"{_pct(report.hit_at_1)} | "
            f"{_pct(report.hit_at_3)} | "
            f"{_pct(report.hit_at_5)} | "
            f"{report.mrr:.3f} | "
            f"{_pct(report.avg_content_match)} | "
            f"{report.avg_latency_ms:.1f} ms |"
        )
    if failures:
        lines.extend(
            [
                "",
                "## Failed Targets",
                "",
                "| Provider | Model | Error |",
                "| --- | --- | --- |",
            ]
        )
        for failure in failures:
            lines.append(
                "| "
                f"{_markdown_table_cell(failure.provider)} | "
                f"{_markdown_table_cell(failure.model)} | "
                f"{_markdown_table_cell(failure.error)} |"
            )
    return "\n".join(lines) + "\n"


def failure_to_dict(failure: TargetFailure) -> dict[str, Any]:
    return {
        "provider": failure.provider,
        "model": failure.model,
        "error": failure.error,
    }


def report_to_dict(
    report: TargetReport,
    *,
    cases: list[GoldenCase] | None = None,
) -> dict[str, Any]:
    case_by_id = {case.id: case for case in cases or []}

    def _case_payload(score: CaseScore) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": score.case_id,
            "query_type": score.query_type,
            "hit_at_1": score.hit_at_1,
            "hit_at_3": score.hit_at_3,
            "hit_at_5": score.hit_at_5,
            "reciprocal_rank": score.reciprocal_rank,
            "best_rank": score.best_rank,
            "best_score": score.best_score,
            "content_match_ratio": score.content_match_ratio,
            "matched_terms": list(score.matched_terms),
            "returned_sources": list(score.returned_sources),
        }
        case = case_by_id.get(score.case_id)
        if case is not None:
            payload.update(
                {
                    "doc_id": case.doc_id,
                    "query": case.query,
                    "expected": {
                        "pages": list(case.expected_pages),
                        "printed_pages": list(case.expected_printed_pages),
                        "section_titles": list(case.expected_section_titles),
                        "block_types": list(case.expected_block_types),
                        "must_contain": list(case.must_contain),
                    },
                    "golden_answer": case.golden_answer,
                }
            )
        return payload

    return {
        "provider": report.provider,
        "model": report.model,
        "collection_name": report.collection_name,
        "case_count": report.case_count,
        "metrics": {
            "hit_at_1": report.hit_at_1,
            "hit_at_3": report.hit_at_3,
            "hit_at_5": report.hit_at_5,
            "mrr": report.mrr,
            "avg_content_match": report.avg_content_match,
            "avg_latency_ms": report.avg_latency_ms,
        },
        "cases": [_case_payload(score) for score in report.scores],
    }
