import argparse
import json
from pathlib import Path

import pytest

from app.evals.rag.evaluation import TargetReport
from app.rag.indexing import ChunkPolicy, get_chunk_policy
from scripts import eval_chunking


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def test_chunk_collection_name_includes_policy_provider_and_model() -> None:
    policy = get_chunk_policy("page_section_window_512")

    assert (
        eval_chunking.chunk_collection_name(policy, "cohere", "embed-v4.0")
        == "mathbird_chunk_page_section_window_512_cohere_embed_v4_0"
    )


@pytest.mark.asyncio
async def test_eval_chunking_cli_writes_dashboard_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden_path = tmp_path / "golden.jsonl"
    output_dir = tmp_path / "results"
    frontend_output = tmp_path / "frontend" / "chunkingEval.generated.json"
    _write_jsonl(
        golden_path,
        [
            {
                "id": "case-1",
                "doc_id": "goodfellow-ch2",
                "query": "What is a vector?",
                "query_type": "definition",
                "expected": {"pages": [2], "must_contain": ["vector"]},
                "golden_answer": "A vector is an ordered array of numbers.",
            }
        ],
    )
    report = TargetReport(
        provider="cohere",
        model="embed-v4.0",
        collection_name="mathbird_chunk_block_cohere_embed_v4_0",
        case_count=1,
        hit_at_1=1.0,
        hit_at_3=1.0,
        hit_at_5=1.0,
        mrr=1.0,
        avg_content_match=1.0,
        avg_latency_ms=12.0,
        scores=(),
        target_id="chunk:block",
        label="Block",
        comparison_axis="chunk_policy",
        metadata={"chunk_policy": "block", "node_count": 3},
    )

    async def fake_evaluate_chunk_policies(**kwargs):
        assert kwargs["policies"][0].name == "block"
        assert "policy_delay_seconds" not in kwargs
        return [report], []

    monkeypatch.setattr(eval_chunking, "evaluate_chunk_policies", fake_evaluate_chunk_policies)

    exit_code = await eval_chunking._amain(
        argparse.Namespace(
            pdf="materials/book.pdf",
            doc_id="goodfellow-ch2",
            golden=str(golden_path),
            provider="cohere",
            model="embed-v4.0",
            top_k=5,
            output_dir=str(output_dir),
            policy=["block"],
            evaluate_existing=False,
            frontend_output=str(frontend_output),
        )
    )

    assert exit_code == 0
    payload = json.loads(next(output_dir.glob("chunking_eval_*.json")).read_text())
    assert payload["schema_version"] == 2
    assert payload["comparison_axis"] == "chunk_policy"
    assert payload["targets"][0]["target_id"] == "chunk:block"
    assert payload["targets"][0]["metadata"] == {"chunk_policy": "block", "node_count": 3}
    assert json.loads(frontend_output.read_text()) == payload


@pytest.mark.asyncio
async def test_evaluate_existing_chunk_policies_skips_parse_and_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policies = (
        ChunkPolicy(name="block", label="Block", description="Baseline"),
        ChunkPolicy(
            name="page_section_window_512",
            label="Page-section window",
            description="Windowed",
        ),
    )
    evaluated_collections: list[str] = []

    def fail_parse(*args, **kwargs):
        raise AssertionError("existing evaluation must not parse the PDF")

    async def fail_index(*args, **kwargs):
        raise AssertionError("existing evaluation must not index chunk policies")

    def fake_load_golden_cases(path: str):
        assert path == "golden.jsonl"
        return []

    async def fake_evaluate_target(*args, **kwargs):
        evaluated_collections.append(kwargs["collection_name"])
        return TargetReport(
            provider="cohere",
            model="embed-v4.0",
            collection_name=kwargs["collection_name"],
            case_count=0,
            hit_at_1=0.0,
            hit_at_3=0.0,
            hit_at_5=0.0,
            mrr=0.0,
            avg_content_match=0.0,
            avg_latency_ms=0.0,
            scores=(),
            target_id=kwargs["target_id"],
            label=kwargs["label"],
            comparison_axis=kwargs["comparison_axis"],
            metadata=kwargs["metadata"],
        )

    monkeypatch.setattr(eval_chunking, "_parse_once", fail_parse)
    monkeypatch.setattr(eval_chunking, "_index_policy", fail_index)
    monkeypatch.setattr(eval_chunking, "load_golden_cases", fake_load_golden_cases)
    monkeypatch.setattr(eval_chunking, "evaluate_target", fake_evaluate_target)

    reports, failures = await eval_chunking.evaluate_existing_chunk_policies(
        golden_path="golden.jsonl",
        provider="cohere",
        model="embed-v4.0",
        top_k=5,
        policies=policies,
    )

    assert failures == []
    assert evaluated_collections == [
        "mathbird_chunk_block_cohere_embed_v4_0",
        "mathbird_chunk_page_section_window_512_cohere_embed_v4_0",
    ]
    assert [report.metadata for report in reports] == [
        {
            "chunk_policy": "block",
            "chunk_policy_label": "Block",
            "chunk_policy_description": "Baseline",
            "embedding_provider": "cohere",
            "embedding_model": "embed-v4.0",
            "evaluation_mode": "existing_collection",
        },
        {
            "chunk_policy": "page_section_window_512",
            "chunk_policy_label": "Page-section window",
            "chunk_policy_description": "Windowed",
            "embedding_provider": "cohere",
            "embedding_model": "embed-v4.0",
            "evaluation_mode": "existing_collection",
        },
    ]
