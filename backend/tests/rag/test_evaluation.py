import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.rag.evaluation import (
    GoldenCase,
    TargetFailure,
    TargetReport,
    aggregate_scores,
    evaluate_target,
    failure_to_dict,
    load_golden_cases,
    render_markdown_report,
    report_to_dict,
    score_case,
)
from app.rag.retriever import RetrievedChunk
from scripts import eval_retrieval as eval_cli


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


MULTILINE_FAILURE_ERROR = (
    'Unexpected Response: 404 (Not Found)\nRaw response content: {"status": "<missing | bad>"}'
)


def test_load_golden_cases_parses_jsonl(tmp_path: Path) -> None:
    golden_path = tmp_path / "golden.jsonl"
    _write_jsonl(
        golden_path,
        [
            {
                "id": "case-1",
                "doc_id": "goodfellow-ch2",
                "query": "What is a vector?",
                "query_type": "definition",
                "expected": {
                    "pages": [2],
                    "printed_pages": [32],
                    "section_titles": ["2.1 Scalars, Vectors, Matrices and Tensors"],
                    "block_types": ["paragraph"],
                    "must_contain": ["vector", "array"],
                },
                "golden_answer": "A vector is an ordered array of numbers.",
            }
        ],
    )

    cases = load_golden_cases(golden_path)

    assert cases == [
        GoldenCase(
            id="case-1",
            doc_id="goodfellow-ch2",
            query="What is a vector?",
            query_type="definition",
            expected_pages=(2,),
            expected_printed_pages=(32,),
            expected_section_titles=("2.1 Scalars, Vectors, Matrices and Tensors",),
            expected_block_types=("paragraph",),
            must_contain=("vector", "array"),
            golden_answer="A vector is an ordered array of numbers.",
        )
    ]


def test_load_golden_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    golden_path = tmp_path / "golden.jsonl"
    row = {
        "id": "case-1",
        "doc_id": "goodfellow-ch2",
        "query": "What is a vector?",
        "query_type": "definition",
        "expected": {"pages": [2], "must_contain": ["vector"]},
        "golden_answer": "A vector is an ordered array of numbers.",
    }
    _write_jsonl(golden_path, [row, row])

    with pytest.raises(ValueError, match="Duplicate golden case id: case-1"):
        load_golden_cases(golden_path)


def test_load_golden_cases_requires_golden_answer(tmp_path: Path) -> None:
    golden_path = tmp_path / "golden.jsonl"
    _write_jsonl(
        golden_path,
        [
            {
                "id": "case-1",
                "doc_id": "goodfellow-ch2",
                "query": "What is a vector?",
                "query_type": "definition",
                "expected": {"pages": [2], "must_contain": ["vector"]},
                "golden_answer": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="case-1.*golden_answer"):
        load_golden_cases(golden_path)


@pytest.mark.parametrize("field", ["doc_id", "query"])
def test_load_golden_cases_requires_doc_id_and_query(tmp_path: Path, field: str) -> None:
    golden_path = tmp_path / "golden.jsonl"
    row = {
        "id": "case-1",
        "doc_id": "goodfellow-ch2",
        "query": "What is a vector?",
        "query_type": "definition",
        "expected": {"pages": [2], "must_contain": ["vector"]},
        "golden_answer": "A vector is an ordered array of numbers.",
    }
    row[field] = ""
    _write_jsonl(golden_path, [row])

    with pytest.raises(ValueError, match=f"case-1.*{field}"):
        load_golden_cases(golden_path)


def _case() -> GoldenCase:
    return GoldenCase(
        id="case-1",
        doc_id="goodfellow-ch2",
        query="What is the Frobenius norm?",
        query_type="definition",
        expected_pages=(10, 17),
        expected_printed_pages=(40, 47),
        expected_section_titles=("2.5 Norms", "2.10 The Trace Operator"),
        expected_block_types=("paragraph", "equation"),
        must_contain=("Frobenius norm", "L2 norm"),
        golden_answer="The Frobenius norm is the square root of summed squared entries.",
    )


def test_score_case_computes_hits_mrr_and_content_match() -> None:
    chunks = [
        RetrievedChunk(text="Unrelated determinant text.", source="book.pdf, page 12", score=0.9),
        RetrievedChunk(
            text="The Frobenius norm is analogous to the L2 norm of a vector.",
            source="deep_learning_ian_goodfellow_chapter_2.pdf, chapter 2, page 10, 2.5 Norms",
            score=0.8,
        ),
    ]

    result = score_case(_case(), chunks)

    assert result.hit_at_1 is False
    assert result.hit_at_3 is True
    assert result.hit_at_5 is True
    assert result.reciprocal_rank == 0.5
    assert result.best_rank == 2
    assert result.best_score == 0.8
    assert result.content_match_ratio == 1.0
    assert result.matched_terms == ("Frobenius norm", "L2 norm")


def test_score_case_handles_miss() -> None:
    result = score_case(
        _case(),
        [RetrievedChunk(text="Only determinant content.", source="book.pdf, page 17", score=0.2)],
    )

    assert result.hit_at_1 is False
    assert result.hit_at_3 is False
    assert result.hit_at_5 is False
    assert result.reciprocal_rank == 0.0
    assert result.best_rank is None
    assert result.content_match_ratio == 0.0
    assert result.matched_terms == ()


def test_score_case_requires_exact_page_token() -> None:
    case = GoldenCase(
        id="case-page-1",
        doc_id="goodfellow-ch2",
        query="What starts the chapter?",
        query_type="definition",
        expected_pages=(1,),
        expected_printed_pages=(31,),
        expected_section_titles=(),
        expected_block_types=("paragraph",),
        must_contain=("linear algebra",),
        golden_answer="The chapter starts by explaining why linear algebra matters.",
    )

    result = score_case(
        case,
        [
            RetrievedChunk(
                text="linear algebra but wrong page",
                source="book.pdf, page 10, 2.5 Norms",
                score=0.9,
            )
        ],
    )

    assert result.hit_at_1 is False
    assert result.best_rank is None
    assert result.returned_sources == ("book.pdf, page 10, 2.5 Norms",)


def test_score_case_requires_expected_page_even_when_section_matches() -> None:
    case = GoldenCase(
        id="case-page-section",
        doc_id="goodfellow-ch2",
        query="Where is broadcasting introduced?",
        query_type="concept",
        expected_pages=(4,),
        expected_printed_pages=(34,),
        expected_section_titles=("2.1 Scalars, Vectors, Matrices and Tensors",),
        expected_block_types=("paragraph",),
        must_contain=("broadcasting",),
        golden_answer="Broadcasting copies a vector across matrix rows implicitly.",
    )

    result = score_case(
        case,
        [
            RetrievedChunk(
                text="broadcasting appears here",
                source="book.pdf, page 14, 2.1 Scalars, Vectors, Matrices and Tensors",
                score=0.9,
            )
        ],
    )

    assert result.hit_at_1 is False
    assert result.best_rank is None


def test_aggregate_scores_computes_target_metrics() -> None:
    scores = [
        score_case(_case(), [RetrievedChunk("Frobenius norm L2 norm", "book.pdf, page 10", 0.9)]),
        score_case(_case(), [RetrievedChunk("miss", "book.pdf, page 1", 0.1)]),
    ]

    report = aggregate_scores(
        provider="openai",
        model="text-embedding-3-small",
        collection_name="mathbird_openai_text_embedding_3_small",
        scores=scores,
        latency_ms=(100.0, 300.0),
    )

    assert report.case_count == 2
    assert report.hit_at_1 == 0.5
    assert report.hit_at_3 == 0.5
    assert report.hit_at_5 == 0.5
    assert report.mrr == 0.5
    assert report.avg_content_match == 0.5
    assert report.avg_latency_ms == 200.0


def test_aggregate_scores_accepts_chunk_target_metadata() -> None:
    scores = [
        score_case(_case(), [RetrievedChunk("Frobenius norm L2 norm", "book.pdf, page 10", 0.9)])
    ]

    report = aggregate_scores(
        provider="cohere",
        model="embed-v4.0",
        collection_name="mathbird_chunk_block_cohere_embed_v4_0",
        scores=scores,
        latency_ms=(100.0,),
        target_id="chunk:block",
        label="Block",
        comparison_axis="chunk_policy",
        metadata={"chunk_policy": "block", "node_count": 42},
    )

    assert report.target_id == "chunk:block"
    assert report.label == "Block"
    assert report.comparison_axis == "chunk_policy"
    assert report.metadata == {"chunk_policy": "block", "node_count": 42}


def test_render_markdown_report_orders_by_hit_at_3_then_mrr() -> None:
    weaker = TargetReport(
        provider="cohere",
        model="embed-v4.0",
        collection_name="mathbird_cohere_embed_v4_0",
        case_count=20,
        hit_at_1=0.2,
        hit_at_3=0.4,
        hit_at_5=0.5,
        mrr=0.3,
        avg_content_match=0.4,
        avg_latency_ms=120.0,
        scores=(),
    )
    stronger = TargetReport(
        provider="openai",
        model="text-embedding-3-large",
        collection_name="mathbird_openai_text_embedding_3_large",
        case_count=20,
        hit_at_1=0.6,
        hit_at_3=0.8,
        hit_at_5=0.9,
        mrr=0.7,
        avg_content_match=0.8,
        avg_latency_ms=180.0,
        scores=(),
    )

    markdown = render_markdown_report([weaker, stronger], golden_path="golden.jsonl", top_k=5)

    assert markdown.index(
        "| text-embedding-3-large | openai | text-embedding-3-large |"
    ) < markdown.index("| embed-v4.0 | cohere | embed-v4.0 |")
    assert (
        "| Target | Provider | Model | Collection | Hit@1 | Hit@3 | Hit@5 | "
        "MRR | Content | Latency |"
        in markdown
    )


def test_failure_to_dict_serializes_target_failure() -> None:
    failure = TargetFailure(
        provider="voyage",
        model="voyage-3-lite",
        error=MULTILINE_FAILURE_ERROR,
    )

    data = failure_to_dict(failure)

    assert data == {
        "provider": "voyage",
        "model": "voyage-3-lite",
        "error": MULTILINE_FAILURE_ERROR,
        "target_id": "voyage:voyage-3-lite",
        "label": "voyage-3-lite",
        "comparison_axis": "embedding_model",
        "metadata": {},
    }


def test_render_markdown_report_includes_failures_after_success_table() -> None:
    report = TargetReport(
        provider="openai",
        model="text-embedding-3-small",
        collection_name="mathbird_openai_text_embedding_3_small",
        case_count=20,
        hit_at_1=0.5,
        hit_at_3=0.7,
        hit_at_5=0.8,
        mrr=0.6,
        avg_content_match=0.7,
        avg_latency_ms=100.0,
        scores=(),
    )
    failure = TargetFailure(
        provider="voyage",
        model="voyage-3-lite",
        error=MULTILINE_FAILURE_ERROR,
    )

    markdown = render_markdown_report(
        [report],
        failures=[failure],
        golden_path="golden.jsonl",
        top_k=5,
    )

    success_row = "| text-embedding-3-small | openai | text-embedding-3-small |"
    failure_header = "## Failed Targets"
    assert success_row in markdown
    assert failure_header in markdown
    assert markdown.index(success_row) < markdown.index(failure_header)
    assert (
        "| voyage | voyage-3-lite | Unexpected Response: 404 (Not Found)<br>"
        'Raw response content: {"status": "&lt;missing \\| bad&gt;"} |' in markdown
    )


@pytest.mark.asyncio
async def test_eval_retrieval_cli_continues_after_target_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden_path = tmp_path / "golden.jsonl"
    output_dir = tmp_path / "results"
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
    successful_report = TargetReport(
        provider="openai",
        model="text-embedding-3-small",
        collection_name="mathbird_openai_text_embedding_3_small",
        case_count=1,
        hit_at_1=1.0,
        hit_at_3=1.0,
        hit_at_5=1.0,
        mrr=1.0,
        avg_content_match=1.0,
        avg_latency_ms=10.0,
        scores=(),
    )

    async def fake_evaluate_target(*args, provider: str, model: str, **kwargs) -> TargetReport:
        if provider == "voyage":
            raise RuntimeError("Collection mathbird_voyage_voyage_3_lite not found")
        return successful_report

    monkeypatch.setattr(eval_cli, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(eval_cli, "evaluate_target", fake_evaluate_target)

    exit_code = await eval_cli._amain(
        argparse.Namespace(
            golden=str(golden_path),
            output_dir=str(output_dir),
            top_k=5,
            target=(
                ("openai", "text-embedding-3-small"),
                ("voyage", "voyage-3-lite"),
            ),
            frontend_output=None,
        )
    )

    assert exit_code == 1
    assert "FAIL voyage/voyage-3-lite: Collection mathbird_voyage_voyage_3_lite not found" in (
        capsys.readouterr().out
    )
    payload = json.loads(next(output_dir.glob("retrieval_eval_*.json")).read_text())
    assert payload["comparison_axis"] == "embedding_model"
    assert payload["targets"][0]["provider"] == "openai"
    assert payload["failures"] == [
        {
            "provider": "voyage",
            "model": "voyage-3-lite",
            "error": "Collection mathbird_voyage_voyage_3_lite not found",
            "target_id": "voyage:voyage-3-lite",
            "label": "voyage-3-lite",
            "comparison_axis": "embedding_model",
            "metadata": {},
        }
    ]
    markdown = next(output_dir.glob("retrieval_eval_*.md")).read_text()
    assert "## Failed Targets" in markdown
    assert (
        "| voyage | voyage-3-lite | Collection mathbird_voyage_voyage_3_lite not found |"
        in markdown
    )


@pytest.mark.asyncio
async def test_eval_retrieval_cli_requires_top_k_at_least_5(tmp_path: Path) -> None:
    golden_path = tmp_path / "golden.jsonl"
    output_dir = tmp_path / "results"
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

    with pytest.raises(ValueError, match="top_k must be at least 5"):
        await eval_cli._amain(
            argparse.Namespace(
                golden=str(golden_path),
                output_dir=str(output_dir),
                top_k=3,
                target=(("openai", "text-embedding-3-small"),),
                frontend_output=None,
            )
        )

    assert not output_dir.exists()


@pytest.mark.asyncio
async def test_evaluate_target_uses_target_settings_and_doc_filter() -> None:
    cases = [_case()]
    fake_stack = MagicMock()
    fake_stack.collection_name = "mathbird_openai_text_embedding_3_small"
    fake_stack.qdrant_client = object()
    fake_retriever = MagicMock()
    fake_retriever.retrieve = AsyncMock(
        return_value=[
            RetrievedChunk(
                text="The Frobenius norm is analogous to the L2 norm.",
                source="book.pdf, page 10, 2.5 Norms",
                score=0.7,
            )
        ]
    )
    base_settings = Settings(_env_file=None, openai_api_key="sk-test")

    with (
        patch("app.rag.evaluation.build_qdrant_index_stack", return_value=fake_stack) as build,
        patch("app.rag.evaluation.LlamaIndexQdrantRetriever", return_value=fake_retriever),
        patch("app.rag.evaluation.close_qdrant_client", new=AsyncMock()) as close_client,
    ):
        report = await evaluate_target(
            cases,
            base_settings=base_settings,
            provider="openai",
            model="text-embedding-3-small",
            top_k=5,
        )

    called_settings = build.call_args.args[0]
    assert called_settings.embedding_provider == "openai"
    assert called_settings.embedding_model == "text-embedding-3-small"
    assert called_settings.qdrant_collection == "auto"
    fake_retriever.retrieve.assert_awaited_once_with(
        "What is the Frobenius norm?",
        top_k=5,
        doc_ids=("goodfellow-ch2",),
    )
    close_client.assert_awaited_once_with(fake_stack.qdrant_client)
    assert report.provider == "openai"
    assert report.model == "text-embedding-3-small"
    assert report.hit_at_1 == 1.0


def test_report_to_dict_serializes_case_scores() -> None:
    case = _case()
    report = aggregate_scores(
        provider="openai",
        model="text-embedding-3-small",
        collection_name="mathbird_openai_text_embedding_3_small",
        scores=[
            score_case(
                case,
                [
                    RetrievedChunk(
                        "The Frobenius norm is analogous to the L2 norm.",
                        "book.pdf, page 10",
                        0.7,
                    )
                ],
            )
        ],
        latency_ms=(10.0,),
    )

    data = report_to_dict(report, cases=[case])

    assert data["provider"] == "openai"
    assert data["metrics"]["hit_at_1"] == 1.0
    assert data["cases"][0]["case_id"] == "case-1"
    assert data["cases"][0]["query"] == "What is the Frobenius norm?"
    assert data["cases"][0]["doc_id"] == "goodfellow-ch2"
    assert data["cases"][0]["expected"]["pages"] == [10, 17]
    assert data["cases"][0]["expected"]["must_contain"] == ["Frobenius norm", "L2 norm"]
    assert data["cases"][0]["returned_sources"] == ["book.pdf, page 10"]


def test_report_to_dict_serializes_target_metadata_for_dashboard() -> None:
    case = _case()
    report = aggregate_scores(
        provider="cohere",
        model="embed-v4.0",
        collection_name="mathbird_chunk_page_section_512_cohere_embed_v4_0",
        scores=[
            score_case(
                case,
                [
                    RetrievedChunk(
                        "The Frobenius norm is analogous to the L2 norm.",
                        "book.pdf, page 10",
                        0.7,
                    )
                ],
            )
        ],
        latency_ms=(10.0,),
        target_id="chunk:page_section_window_512",
        label="Page-section window",
        comparison_axis="chunk_policy",
        metadata={
            "chunk_policy": "page_section_window_512",
            "embedding_provider": "cohere",
            "embedding_model": "embed-v4.0",
            "node_count": 120,
        },
    )

    data = report_to_dict(report, cases=[case])

    assert data["target_id"] == "chunk:page_section_window_512"
    assert data["label"] == "Page-section window"
    assert data["comparison_axis"] == "chunk_policy"
    assert data["metadata"] == {
        "chunk_policy": "page_section_window_512",
        "embedding_provider": "cohere",
        "embedding_model": "embed-v4.0",
        "node_count": 120,
    }


def test_score_case_matches_printed_page_in_source() -> None:
    case = GoldenCase(
        id="case-printed",
        doc_id="goodfellow-ch2",
        query="page 37",
        query_type="structured_page",
        expected_pages=(7,),
        expected_printed_pages=(37,),
        expected_section_titles=(),
        expected_block_types=(),
        must_contain=("theoretical tool",),
        golden_answer="Inverse caution on printed page 37.",
    )

    score = score_case(
        case,
        [
            RetrievedChunk(
                "The inverse is mainly a theoretical tool.",
                "book.pdf, chapter 2, page 37",
                1.0,
            )
        ],
    )

    assert score.hit_at_1 is True


def test_load_structured_golden_cases_parses_jsonl(tmp_path: Path) -> None:
    from app.rag.evaluation import StructuredGoldenCase, load_structured_golden_cases

    golden_path = tmp_path / "structured.jsonl"
    _write_jsonl(
        golden_path,
        [
            {
                "id": "case-1",
                "doc_id": "goodfellow-ch2",
                "query": "section 2.7",
                "query_type": "structured_section",
                "expects_structured_route": True,
                "expected": {
                    "printed_pages": [44],
                    "must_contain": ["eigenvector"],
                },
                "golden_answer": "Section 2.7 covers eigendecomposition.",
            }
        ],
    )

    cases = load_structured_golden_cases(golden_path)

    assert cases == [
        StructuredGoldenCase(
            id="case-1",
            doc_id="goodfellow-ch2",
            query="section 2.7",
            query_type="structured_section",
            expected_pages=(),
            expected_printed_pages=(44,),
            must_contain=("eigenvector",),
            golden_answer="Section 2.7 covers eigendecomposition.",
            expects_structured_route=True,
        )
    ]
