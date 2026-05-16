"""LlamaParse/LlamaCloud adapter for textbook PDFs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.rag.normalizer import normalize_llamaparse_items
from app.rag.parsing import ParsedDocument


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class LlamaParseError(RuntimeError):
    """Raised when LlamaParse cannot parse a document."""


class LlamaParseParser:
    def __init__(
        self,
        *,
        api_key: str,
        tier: str = "agentic",
        version: str = "latest",
        client: Any | None = None,
        poll_interval_seconds: float = 2.0,
        max_polls: int = 900,
    ) -> None:
        self.api_key = api_key
        self.tier = tier
        self.version = version
        self.client = client
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        from llama_cloud import AsyncLlamaCloud

        self.client = AsyncLlamaCloud(api_key=self.api_key)
        return self.client

    async def parse_pdf(self, path: str, *, doc_id: str, filename: str) -> ParsedDocument:
        client = self._client()
        file_result = await client.files.create(file=Path(path), purpose="parse")
        file_id = _get(file_result, "id")
        if not file_id:
            raise LlamaParseError("LlamaParse file upload did not return a file id.")

        job = await client.parsing.create(
            file_id=file_id,
            tier=self.tier,
            version=self.version,
            output_options={
                "images_to_save": ["embedded", "layout"],
                "extract_printed_page_number": True,
                "markdown": {
                    "inline_images": False,
                    "tables": {"output_tables_as_markdown": True},
                },
            },
            processing_options={
                "aggressive_table_extraction": True,
                "specialized_chart_parsing": "agentic",
            },
            agentic_options={
                "custom_prompt": (
                    "Parse this as a math textbook. Preserve equations, examples, "
                    "exercises, page numbers, tables, graphs, and diagram descriptions."
                )
            },
        )
        job_id = _get(job, "id")
        if not job_id:
            raise LlamaParseError("LlamaParse parse request did not return a job id.")

        result = await self._poll_parse_result(client, job_id)
        return normalize_llamaparse_items(result, doc_id=doc_id, filename=filename)

    async def _poll_parse_result(self, client: Any, job_id: str) -> Any:
        expand = ["items", "markdown", "images_content_metadata", "job_metadata"]
        for poll_index in range(self.max_polls):
            result = await client.parsing.get(job_id, expand=expand)
            job = _get(result, "job", {}) or {}
            status = str(_get(job, "status", "")).upper()

            if status == "COMPLETED":
                return result
            if status in {"FAILED", "CANCELLED"}:
                message = _get(job, "error_message", "") or f"LlamaParse job {status.lower()}."
                raise LlamaParseError(str(message))

            if poll_index < self.max_polls - 1:
                await asyncio.sleep(self.poll_interval_seconds)

        raise LlamaParseError("Timed out waiting for LlamaParse parse job.")
