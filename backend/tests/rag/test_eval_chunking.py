import argparse
import json
from pathlib import Path

import pytest

from app.rag.evaluation import TargetReport
from app.rag.indexing import get_chunk_policy
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
    frontend_output = tmp_path / "frontend" / "retrievalEval.generated.json"
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
