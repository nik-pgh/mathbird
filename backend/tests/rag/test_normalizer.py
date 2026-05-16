import builtins

import pytest

from app.rag.llamaparse_parser import LlamaParseError, LlamaParseParser
from app.rag.normalizer import normalize_llamaparse_items
from app.rag.parsing import (
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    RetrievalRequest,
    RetrievedContext,
    RetrievedRecord,
)


class _Object:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class FakeFiles:
    def __init__(self, file_id: str | None = "file-123") -> None:
        self.file_id = file_id

    async def create(self, *, file, purpose):
        assert purpose == "parse"
        return type("FileResult", (), {"id": self.file_id})()


class FakeParsing:
    def __init__(
        self,
        *,
        job_id: str | None = "job-123",
        statuses: tuple[str, ...] = ("RUNNING", "COMPLETED"),
        error_message: str = "",
    ) -> None:
        self.calls = 0
        self.job_id = job_id
        self.statuses = statuses
        self.error_message = error_message
        self.create_kwargs = {}

    async def create(self, **kwargs):
        self.create_kwargs = kwargs
        assert kwargs["file_id"] == "file-123"
        assert kwargs["tier"] == "agentic"
        assert kwargs["version"] == "latest"
        return type("Job", (), {"id": self.job_id})()

    async def get(self, job_id, *, expand):
        self.calls += 1
        assert job_id == "job-123"
        assert "items" in expand
        status_index = min(self.calls - 1, len(self.statuses) - 1)
        job = {"status": self.statuses[status_index]}
        if self.error_message:
            job["error_message"] = self.error_message
        return {
            "job": job,
            "items": {
                "pages": [
                    {
                        "page": 1,
                        "items": [
                            {
                                "type": "text",
                                "value": "Problem 1. Add 2 + 2.",
                                "md": "Problem 1. Add 2 + 2.",
                            }
                        ],
                    }
                ]
            },
        }


class FakeLlamaCloudClient:
    def __init__(
        self,
        *,
        file_id: str | None = "file-123",
        job_id: str | None = "job-123",
        statuses: tuple[str, ...] = ("RUNNING", "COMPLETED"),
        error_message: str = "",
    ) -> None:
        self.files = FakeFiles(file_id)
        self.parsing = FakeParsing(
            job_id=job_id,
            statuses=statuses,
            error_message=error_message,
        )


@pytest.mark.asyncio
async def test_llamaparse_parser_polls_and_normalizes(tmp_path) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    parser = LlamaParseParser(
        api_key="llx-test",
        client=FakeLlamaCloudClient(),
        poll_interval_seconds=0,
    )

    doc = await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")

    assert doc.doc_id == "doc-1"
    assert doc.pages[0].blocks[0].block_type == "exercise"
    assert parser.client.parsing.create_kwargs["output_options"] == {
        "images_to_save": ["embedded", "layout"],
        "extract_printed_page_number": True,
        "markdown": {
            "inline_images": False,
            "tables": {"output_tables_as_markdown": True},
        },
    }
    assert parser.client.parsing.create_kwargs["processing_options"] == {
        "aggressive_table_extraction": True,
        "specialized_chart_parsing": "agentic",
    }


@pytest.mark.asyncio
async def test_llamaparse_parser_failed_status_raises_error(tmp_path) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    parser = LlamaParseParser(
        api_key="llx-test",
        client=FakeLlamaCloudClient(statuses=("FAILED",), error_message="parse failed"),
        poll_interval_seconds=0,
    )

    with pytest.raises(LlamaParseError, match="parse failed"):
        await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")


@pytest.mark.asyncio
async def test_llamaparse_parser_cancelled_status_raises_error(tmp_path) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    parser = LlamaParseParser(
        api_key="llx-test",
        client=FakeLlamaCloudClient(statuses=("CANCELLED",)),
        poll_interval_seconds=0,
    )

    with pytest.raises(LlamaParseError, match="cancelled"):
        await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")


@pytest.mark.asyncio
async def test_llamaparse_parser_missing_file_id_raises_error(tmp_path) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    parser = LlamaParseParser(
        api_key="llx-test",
        client=FakeLlamaCloudClient(file_id=None),
        poll_interval_seconds=0,
    )

    with pytest.raises(LlamaParseError, match="file upload did not return a file id"):
        await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")


@pytest.mark.asyncio
async def test_llamaparse_parser_missing_job_id_raises_error(tmp_path) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    parser = LlamaParseParser(
        api_key="llx-test",
        client=FakeLlamaCloudClient(job_id=None),
        poll_interval_seconds=0,
    )

    with pytest.raises(LlamaParseError, match="parse request did not return a job id"):
        await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")


@pytest.mark.asyncio
async def test_llamaparse_parser_timeout_raises_without_final_sleep(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("app.rag.llamaparse_parser.asyncio.sleep", fake_sleep)
    parser = LlamaParseParser(
        api_key="llx-test",
        client=FakeLlamaCloudClient(statuses=("RUNNING",)),
        poll_interval_seconds=0.25,
        max_polls=1,
    )

    with pytest.raises(LlamaParseError, match="Timed out"):
        await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")

    assert sleeps == []


@pytest.mark.asyncio
async def test_llamaparse_parser_uses_injected_client_without_importing_llama_cloud(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    client = FakeLlamaCloudClient(statuses=("COMPLETED",))
    real_import = builtins.__import__

    def reject_llama_cloud_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "llama_cloud":
            raise AssertionError("llama_cloud should not be imported when client is injected")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", reject_llama_cloud_import)
    parser = LlamaParseParser(api_key="llx-test", client=client, poll_interval_seconds=0)

    doc = await parser.parse_pdf(str(pdf), doc_id="doc-1", filename="book.pdf")

    assert parser.client is client
    assert doc.doc_id == "doc-1"


def test_parsed_block_source_label_includes_problem_number() -> None:
    doc = ParsedDocument(
        doc_id="doc-1",
        filename="Spectrum Math 6.pdf",
        pages=[
            ParsedPage(
                page_number=37,
                text="Problem 8. Solve 2x + 3 = 9.",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p37:b0",
                        page_number=37,
                        block_type="exercise",
                        text="Problem 8. Solve 2x + 3 = 9.",
                        markdown="Problem 8. Solve 2x + 3 = 9.",
                        exercise_number="8",
                    )
                ],
            )
        ],
    )

    assert doc.page_count == 1
    assert doc.pages[0].blocks[0].source_label("Spectrum Math 6.pdf") == (
        "Spectrum Math 6.pdf, page 37, problem 8"
    )


def test_parsed_block_source_label_includes_example_number() -> None:
    block = ParsedBlock(
        block_id="doc-1:p20:b0",
        page_number=20,
        block_type="example",
        text="Example 3. Factor x^2 + 5x + 6.",
        example_number="3",
    )
    record = RetrievedRecord(
        text=block.text,
        filename="book.pdf",
        page_number=20,
        block_type="example",
        example_number="3",
    )

    assert block.source_label("book.pdf") == "book.pdf, page 20, example 3"
    assert record.source == "book.pdf, page 20, example 3"


def test_parsed_models_coerce_collections_to_tuples() -> None:
    bbox = [0.1, 0.2, 0.3, 0.4]
    block = ParsedBlock(
        block_id="doc-1:p37:b0",
        page_number=37,
        block_type="exercise",
        text="Problem 8. Solve 2x + 3 = 9.",
        image_refs=["graph-1.png"],
        bbox=bbox,
        neighboring_block_ids=["doc-1:p37:b1"],
    )
    page = ParsedPage(page_number=37, text=block.text, blocks=[block])
    doc = ParsedDocument(doc_id="doc-1", filename="Spectrum Math 6.pdf", pages=[page])
    request = RetrievalRequest(
        query="solve",
        doc_ids=["doc-1"],
        requested_modalities=["text", "image"],
    )
    record = RetrievedRecord(
        text=block.text,
        filename=doc.filename,
        page_number=37,
        visual_refs=["graph-1.png"],
    )
    context = RetrievedContext(
        records=[record],
        citations=["Spectrum Math 6.pdf, page 37"],
        visual_refs=["graph-1.png"],
    )
    bbox[0] = 9.9

    assert block.image_refs == ("graph-1.png",)
    assert block.bbox == (0.1, 0.2, 0.3, 0.4)
    assert block.neighboring_block_ids == ("doc-1:p37:b1",)
    assert page.blocks == (block,)
    assert doc.pages == (page,)
    assert request.doc_ids == ("doc-1",)
    assert request.requested_modalities == ("text", "image")
    assert record.visual_refs == ("graph-1.png",)
    assert context.records == (record,)
    assert context.citations == ("Spectrum Math 6.pdf, page 37",)
    assert context.visual_refs == ("graph-1.png",)


def test_retrieval_request_student_context_is_copied_read_only_mapping() -> None:
    student_context = {
        "grade": 6,
        "progress": {
            "completed": ["lesson-1"],
            "scores": [{"lesson": "lesson-1", "score": 90}],
        },
        "standards": {"6.EE.A.2"},
    }
    request = RetrievalRequest(query="solve", student_context=student_context)

    student_context["grade"] = 7
    student_context["progress"]["completed"].append("lesson-2")
    student_context["progress"]["scores"][0]["score"] = 50
    student_context["standards"].add("6.EE.B.5")

    assert request.student_context["grade"] == 6
    assert request.student_context["progress"]["completed"] == ("lesson-1",)
    assert request.student_context["progress"]["scores"][0]["score"] == 90
    assert request.student_context["standards"] == frozenset({"6.EE.A.2"})
    with pytest.raises(TypeError):
        request.student_context["grade"] = 8
    with pytest.raises(TypeError):
        request.student_context["progress"]["scores"][0]["score"] = 75


def test_content_for_embedding_uses_text_for_blank_markdown_and_includes_modalities() -> None:
    block = ParsedBlock(
        block_id="doc-1:p37:b1",
        page_number=37,
        block_type="equation",
        text="Solve 2x + 3 = 9.",
        markdown="   ",
        latex="2x + 3 = 9",
        image_refs=("graph-1.png", "diagram-2.png"),
    )

    assert block.content_for_embedding() == (
        "Solve 2x + 3 = 9.\nEquation: 2x + 3 = 9\nVisual references: graph-1.png, diagram-2.png"
    )


def test_normalize_llamaparse_items_detects_heading_exercise_and_neighbors() -> None:
    payload = {
        "items": {
            "pages": [
                {
                    "page": 37,
                    "items": [
                        {
                            "type": "heading",
                            "value": "Solving Equations",
                            "md": "# Solving Equations",
                        },
                        {
                            "type": "text",
                            "value": "Example 2. Solve x + 4 = 10.",
                            "md": "Example 2. Solve x + 4 = 10.",
                        },
                        {
                            "type": "text",
                            "value": "Problem 8. Solve 2x + 3 = 9.",
                            "md": "Problem 8. Solve 2x + 3 = 9.",
                        },
                    ],
                }
            ]
        }
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="Spectrum Math 6.pdf")

    assert doc.pages[0].page_number == 37
    assert doc.pages[0].blocks[0].block_type == "heading"
    assert doc.pages[0].blocks[1].block_type == "example"
    assert doc.pages[0].blocks[1].example_number == "2"
    assert doc.pages[0].blocks[2].block_type == "exercise"
    assert doc.pages[0].blocks[2].exercise_number == "8"
    assert doc.pages[0].blocks[2].section_title == "Solving Equations"
    assert doc.pages[0].blocks[2].neighboring_block_ids == ("doc-1:p37:b1",)


@pytest.mark.parametrize(
    "label",
    ["8. Solve 2x + 3 = 9.", "8) Solve 2x + 3 = 9.", "(8) Solve 2x + 3 = 9."],
)
def test_normalize_llamaparse_items_detects_numbered_exercise_labels(label: str) -> None:
    payload = {
        "items": {
            "pages": [
                {
                    "page": 37,
                    "items": [{"type": "text", "value": label, "md": label}],
                }
            ]
        }
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].block_type == "exercise"
    assert doc.pages[0].blocks[0].exercise_number == "8"


def test_normalize_llamaparse_items_preserves_image_refs() -> None:
    payload = {
        "items": {
            "pages": [
                {
                    "page": 5,
                    "items": [
                        {
                            "type": "image",
                            "value": "Coordinate graph showing a line.",
                            "md": "![graph](image_0.png)",
                            "image_filename": "image_0.png",
                        }
                    ],
                }
            ]
        },
        "images_content_metadata": {
            "images": [
                {
                    "filename": "image_0.png",
                    "category": "layout",
                    "presigned_url": "https://example.com/image_0.png",
                }
            ]
        },
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].block_type == "image"
    assert doc.pages[0].blocks[0].image_refs == ("doc-1:image_0.png",)


def test_normalize_llamaparse_items_accepts_top_level_pages_payload() -> None:
    payload = {
        "pages": [
            {
                "page": 9,
                "items": [
                    {
                        "type": "text",
                        "value": "Read the directions carefully.",
                        "md": "Read the directions carefully.",
                    }
                ],
            }
        ]
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].page_number == 9
    assert doc.pages[0].blocks[0].text == "Read the directions carefully."


def test_normalize_llamaparse_items_accepts_object_payload_and_camel_case_bbox() -> None:
    payload = _Object(
        pages=[
            _Object(
                page=4,
                items=[
                    _Object(
                        type="text",
                        value="Problem 3. Solve y - 2 = 5.",
                        md="Problem 3. Solve y - 2 = 5.",
                        bBox=_Object(x=1, y=2, w=3, h=4),
                    )
                ],
            )
        ]
    )

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].block_type == "exercise"
    assert doc.pages[0].blocks[0].bbox == (1.0, 2.0, 3.0, 4.0)


def test_normalize_llamaparse_items_ignores_incomplete_bbox() -> None:
    payload = {
        "pages": [
            {
                "page": 4,
                "items": [
                    {
                        "type": "text",
                        "value": "Problem 3. Solve y - 2 = 5.",
                        "bBox": {"x": 1, "y": None, "w": 3},
                    }
                ],
            }
        ]
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].bbox is None


def test_normalize_llamaparse_items_uses_page_level_image_names() -> None:
    payload = {
        "pages": [
            {
                "page": 5,
                "items": [
                    {
                        "type": "image",
                        "value": "Coordinate graph showing a line.",
                    }
                ],
                "images": [
                    {
                        "name": "figures/image_1.png",
                        "presigned_url": "https://example.com/private/image_1.png?sig=abc",
                    }
                ],
            }
        ]
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].image_refs == ("doc-1:image_1.png",)


def test_normalize_llamaparse_items_extracts_stable_markdown_image_refs() -> None:
    payload = {
        "pages": [
            {
                "page": 5,
                "items": [
                    {
                        "type": "image",
                        "value": "Coordinate graph showing a line.",
                        "md": "![graph](https://cdn.example.com/books/figures/image_2.png?token=secret)",
                    }
                ],
            }
        ]
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].image_refs == ("doc-1:image_2.png",)


def test_normalize_llamaparse_items_carries_section_title_across_pages() -> None:
    payload = {
        "pages": [
            {
                "page": 1,
                "items": [
                    {"type": "heading", "value": "Ratios", "md": "# Ratios"},
                    {"type": "text", "value": "A ratio compares two quantities."},
                ],
            },
            {
                "page": 2,
                "items": [
                    {"type": "text", "value": "Problem 4. Write the ratio of 3 to 5."},
                    {"type": "heading", "value": "Rates", "md": "# Rates"},
                    {"type": "text", "value": "Problem 5. Find the unit rate."},
                ],
            },
        ]
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[1].blocks[0].section_title == "Ratios"
    assert doc.pages[1].blocks[2].section_title == "Rates"


def test_normalize_llamaparse_items_classifies_equations() -> None:
    payload = {
        "pages": [
            {
                "page": 6,
                "items": [
                    {
                        "type": "text",
                        "value": "",
                        "md": "$$2x + 3 = 9$$",
                    }
                ],
            }
        ]
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].block_type == "equation"
    assert doc.pages[0].blocks[0].latex == "$$2x + 3 = 9$$"
