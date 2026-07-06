import argparse
import json
from pathlib import Path

import pytest

from app.rag.evaluation import (
    StructuredCaseScore,
    TargetReport,
    load_structured_golden_cases,
    score_case,
    structured_case_to_golden,
)
from app.rag.retriever import RetrievedChunk
from app.rag.structured_eval_output import (
    extract_chunk_policy_from_collection,
    structured_eval_frontend_filename,
    structured_eval_frontend_path,
)
from scripts import eval_structured


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def test_structured_eval_frontend_filename_for_policies() -> None:
    assert (
        structured_eval_frontend_filename("math_object_window_page_anchor")
        == "structuredEval.mathObjectWindowPageAnchor.generated.json"
    )
    assert (
        structured_eval_frontend_filename("block_neighbor_1")
        == "structuredEval.blockNeighbor.generated.json"
    )


def test_extract_chunk_policy_from_collection() -> None:
    assert (
        extract_chunk_policy_from_collection(
            "mathbird_chunk_math_object_window_page_anchor_google_gemini_embedding_001"
        )
        == "math_object_window_page_anchor"
    )
    assert (
        extract_chunk_policy_from_collection(
            "mathbird_chunk_math_object_window_google_gemini_embedding_001"
        )
        == "math_object_window"
    )


@pytest.mark.asyncio
async def test_eval_structured_cli_writes_dashboard_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden_path = tmp_path / "structured.jsonl"
    output_dir = tmp_path / "results"
    frontend_data_dir = tmp_path / "frontend"
    collection_name = "mathbird_chunk_math_object_window_cohere_embed_v4_0"
    expected_frontend = structured_eval_frontend_path(frontend_data_dir, "math_object_window")
    _write_jsonl(
        golden_path,
        [
            {
                "id": "case-1",
                "doc_id": "goodfellow-ch2",
                "query": "page 44",
                "query_type": "structured_page",
                "expects_structured_route": True,
                "expected": {
                    "pages": [14],
                    "printed_pages": [44],
                    "must_contain": ["symmetric"],
                },
                "golden_answer": "Page 44 covers symmetric eigendecomposition.",
            }
        ],
    )
    golden = structured_case_to_golden(load_structured_golden_cases(golden_path)[0])
    base_score = score_case(
        golden,
        [RetrievedChunk("Symmetric matrix eigendecomposition.", "book.pdf, page 44", 1.0)],
    )
    structured_score = StructuredCaseScore(
        case_id=base_score.case_id,
        query_type=base_score.query_type,
        hit_at_1=base_score.hit_at_1,
        hit_at_3=base_score.hit_at_3,
        hit_at_5=base_score.hit_at_5,
        reciprocal_rank=base_score.reciprocal_rank,
        best_rank=base_score.best_rank,
        best_score=base_score.best_score,
        content_match_ratio=base_score.content_match_ratio,
        matched_terms=base_score.matched_terms,
        returned_sources=base_score.returned_sources,
        retrieval_path="structured",
        routing_correct=True,
        structured_route=True,
        structured_hit_at_1=True,
        structured_latency_ms=3.0,
        semantic_latency_ms=None,
    )
    reports = [
        TargetReport(
            provider="cohere",
            model="embed-v4.0",
            collection_name=collection_name,
            case_count=1,
            hit_at_1=1.0,
            hit_at_3=1.0,
            hit_at_5=1.0,
            mrr=1.0,
            avg_content_match=1.0,
            avg_latency_ms=5.0,
            scores=(structured_score,),
            target_id="path:production",
            label="Production retrieve()",
            comparison_axis="structured_lookup",
            metadata={"path": "production"},
        ),
        TargetReport(
            provider="cohere",
            model="embed-v4.0",
            collection_name=collection_name,
            case_count=1,
            hit_at_1=1.0,
            hit_at_3=1.0,
            hit_at_5=1.0,
            mrr=1.0,
            avg_content_match=1.0,
            avg_latency_ms=3.0,
            scores=(base_score,),
            target_id="path:structured_only",
            label="Structured lookup only",
            comparison_axis="structured_lookup",
            metadata={"path": "structured_only"},
        ),
        TargetReport(
            provider="cohere",
            model="embed-v4.0",
            collection_name=collection_name,
            case_count=1,
            hit_at_1=0.0,
            hit_at_3=1.0,
            hit_at_5=1.0,
            mrr=0.5,
            avg_content_match=1.0,
            avg_latency_ms=40.0,
            scores=(base_score,),
            target_id="path:semantic_only",
            label="Semantic search only",
            comparison_axis="structured_lookup",
            metadata={"path": "semantic_only"},
        ),
    ]

    async def fake_evaluate_structured_paths(*_args, **_kwargs):
        return reports

    class FakeSettings:
        embedding_provider = "cohere"
        embedding_model = "embed-v4.0"
        resolved_qdrant_collection = collection_name

    monkeypatch.setattr(
        eval_structured,
        "evaluate_structured_paths",
        fake_evaluate_structured_paths,
    )
    monkeypatch.setattr(eval_structured, "get_settings", lambda: FakeSettings())

    exit_code = await eval_structured._amain(
        argparse.Namespace(
            golden=str(golden_path),
            top_k=5,
            output_dir=str(output_dir),
            frontend_data_dir=str(frontend_data_dir),
        )
    )

    assert exit_code == 0
    payload = json.loads(expected_frontend.read_text())
    assert payload["comparison_axis"] == "structured_lookup"
    assert len(payload["targets"]) == 3
    assert payload["targets"][0]["target_id"] == "path:production"
    assert payload["targets"][0]["cases"][0]["retrieval_path"] == "structured"
