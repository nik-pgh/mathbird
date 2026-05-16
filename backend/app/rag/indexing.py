"""LlamaIndex node construction for parsed textbook blocks."""

from __future__ import annotations

from llama_index.core.schema import TextNode

from app.rag.parsing import ParsedDocument


def parsed_document_to_nodes(document: ParsedDocument) -> list[TextNode]:
    nodes: list[TextNode] = []

    for page in document.pages:
        for block in page.blocks:
            content = block.content_for_embedding().strip()
            if not content:
                continue

            metadata = {
                "doc_id": document.doc_id,
                "filename": document.filename,
                "page_number": block.page_number,
                "section_title": block.section_title,
                "block_type": block.block_type,
                "exercise_number": block.exercise_number,
                "block_id": block.block_id,
                "neighboring_block_ids": list(block.neighboring_block_ids),
                "visual_refs": list(block.image_refs),
            }

            nodes.append(
                TextNode(
                    id_=block.block_id,
                    text=content,
                    metadata=metadata,
                    excluded_embed_metadata_keys=["filename"],
                    excluded_llm_metadata_keys=["neighboring_block_ids"],
                )
            )

    return nodes
