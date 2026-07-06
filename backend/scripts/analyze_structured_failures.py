"""Classify structured eval production failures as metadata vs ranking misses."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FailureClass = Literal[
    "ranking_miss",
    "metadata_miss",
    "recall_miss",
    "routing_miss",
    "negative_control",
]


@dataclass(frozen=True)
class FailureAnalysis:
    case_id: str
    query: str
    query_type: str
    failure_class: FailureClass
    rationale: str
    best_rank: int | None
    hit_at_3: bool
    hit_at_5: bool
    content_match_ratio: float
    matched_terms: tuple[str, ...]
    retrieval_path: str
    routing_correct: bool
    structured_hit_at_1: bool
    returned_sources: tuple[str, ...]
    expected_pages: tuple[int, ...]
    expected_printed_pages: tuple[int, ...]
    must_contain: tuple[str, ...]


def _page_in_source(source: str, pages: tuple[int, ...]) -> bool:
    return any(re.search(rf"\bpage\s*{page}\b", source, re.I) for page in pages)


def _any_page_match(sources: tuple[str, ...], pages: tuple[int, ...]) -> bool:
    return any(_page_in_source(source, pages) for source in sources)


def classify_failure(case: dict[str, Any]) -> FailureAnalysis:
    case_id = str(case["case_id"])
    query = str(case.get("query", ""))
    query_type = str(case.get("query_type", ""))
    best_rank = case.get("best_rank")
    hit_at_3 = bool(case.get("hit_at_3"))
    hit_at_5 = bool(case.get("hit_at_5"))
    content_match_ratio = float(case.get("content_match_ratio", 0.0))
    matched_terms = tuple(case.get("matched_terms") or ())
    retrieval_path = str(case.get("retrieval_path", ""))
    routing_correct = bool(case.get("routing_correct", True))
    structured_hit_at_1 = bool(case.get("structured_hit_at_1", False))
    returned_sources = tuple(case.get("returned_sources") or [])
    expected = case.get("expected") or {}
    expected_pages = tuple(int(p) for p in expected.get("pages") or [])
    expected_printed_pages = tuple(int(p) for p in expected.get("printed_pages") or [])
    must_contain = tuple(expected.get("must_contain") or [])
    expects_structured = bool(case.get("expects_structured_route", True))
    page_numbers = expected_pages + expected_printed_pages

    if query_type == "negative_routing":
        return FailureAnalysis(
            case_id=case_id,
            query=query,
            query_type=query_type,
            failure_class="negative_control",
            rationale="Negative routing control case; miss is expected behavior.",
            best_rank=best_rank,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            content_match_ratio=content_match_ratio,
            matched_terms=matched_terms,
            retrieval_path=retrieval_path,
            routing_correct=routing_correct,
            structured_hit_at_1=structured_hit_at_1,
            returned_sources=returned_sources,
            expected_pages=expected_pages,
            expected_printed_pages=expected_printed_pages,
            must_contain=must_contain,
        )

    if not routing_correct:
        return FailureAnalysis(
            case_id=case_id,
            query=query,
            query_type=query_type,
            failure_class="routing_miss",
            rationale=(
                f"Query parser routed structured={case.get('structured_route')} "
                f"but golden expects structured={expects_structured}."
            ),
            best_rank=best_rank,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            content_match_ratio=content_match_ratio,
            matched_terms=matched_terms,
            retrieval_path=retrieval_path,
            routing_correct=routing_correct,
            structured_hit_at_1=structured_hit_at_1,
            returned_sources=returned_sources,
            expected_pages=expected_pages,
            expected_printed_pages=expected_printed_pages,
            must_contain=must_contain,
        )

    if best_rank is None or content_match_ratio == 0.0:
        page_ok = _any_page_match(returned_sources, page_numbers) if page_numbers else True
        if not page_ok:
            rationale = (
                "Expected page not present in top-k sources; likely missing/wrong "
                "printed_page_number or filter metadata."
            )
        elif retrieval_path == "structured_fallback_semantic":
            rationale = (
                "Structured lookup returned empty and semantic fallback missed "
                "must_contain terms in top-k."
            )
        elif retrieval_path == "structured" and not structured_hit_at_1:
            rationale = (
                "Structured path returned results on expected page but none "
                "contain required terms — chunk text/metadata gap."
            )
        else:
            rationale = "No matching chunk in top-k (page+term gate failed)."
        return FailureAnalysis(
            case_id=case_id,
            query=query,
            query_type=query_type,
            failure_class="metadata_miss" if retrieval_path == "structured" else "recall_miss",
            rationale=rationale,
            best_rank=best_rank,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            content_match_ratio=content_match_ratio,
            matched_terms=matched_terms,
            retrieval_path=retrieval_path,
            routing_correct=routing_correct,
            structured_hit_at_1=structured_hit_at_1,
            returned_sources=returned_sources,
            expected_pages=expected_pages,
            expected_printed_pages=expected_printed_pages,
            must_contain=must_contain,
        )

    if best_rank is not None and best_rank > 1:
        page_ok = _any_page_match(returned_sources[:1], page_numbers)
        rationale = (
            f"Matching chunk at rank {best_rank}; rank-1 source is "
            f"{'on expected page but wrong block' if page_ok else 'off-page or wrong block'}."
        )
        return FailureAnalysis(
            case_id=case_id,
            query=query,
            query_type=query_type,
            failure_class="ranking_miss",
            rationale=rationale,
            best_rank=best_rank,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            content_match_ratio=content_match_ratio,
            matched_terms=matched_terms,
            retrieval_path=retrieval_path,
            routing_correct=routing_correct,
            structured_hit_at_1=structured_hit_at_1,
            returned_sources=returned_sources,
            expected_pages=expected_pages,
            expected_printed_pages=expected_printed_pages,
            must_contain=must_contain,
        )

    raise ValueError(f"Case {case_id} is not a production failure")


def load_production_failures(report_path: Path) -> list[dict[str, Any]]:
    data = json.loads(report_path.read_text())
    production = next(t for t in data["targets"] if t["target_id"] == "path:production")
    return [case for case in production["cases"] if not case["hit_at_1"]]


def main() -> int:
    report_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "../frontend/src/data/structuredEval.mathObjectWindowPageAnchor.generated.json"
    )
    failures = load_production_failures(report_path)
    analyses = [classify_failure(case) for case in failures]

    counts = Counter(a.failure_class for a in analyses)
    print(f"Production failures: {len(analyses)} / 40")
    print("Classification:")
    for cls, count in sorted(counts.items()):
        print(f"  {cls}: {count}")
    print()

    for analysis in analyses:
        print(f"## {analysis.case_id} ({analysis.query_type})")
        print(f"query: {analysis.query!r}")
        print(f"class: {analysis.failure_class}")
        print(f"path: {analysis.retrieval_path} | structured_hit@1: {analysis.structured_hit_at_1}")
        print(f"best_rank: {analysis.best_rank} | hit@3: {analysis.hit_at_3} | hit@5: {analysis.hit_at_5}")
        print(f"content_match: {analysis.content_match_ratio:.2f} | matched: {analysis.matched_terms}")
        print(f"expected pages/pdf: {analysis.expected_pages} / printed {analysis.expected_printed_pages}")
        print(f"must_contain: {analysis.must_contain}")
        print(f"rationale: {analysis.rationale}")
        print("rank-1:", analysis.returned_sources[0] if analysis.returned_sources else "(none)")
        if analysis.best_rank and analysis.best_rank <= len(analysis.returned_sources):
            print(f"best match:", analysis.returned_sources[analysis.best_rank - 1])
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
