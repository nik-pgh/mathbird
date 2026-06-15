"""LlamaIndex node construction for parsed textbook blocks."""

from __future__ import annotations

import uuid

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
                "textbook_doc_id": document.doc_id,
                "filename": document.filename,
                "page_number": block.page_number,
                "section_title": block.section_title,
                "chapter_number": block.chapter_number,
                "block_type": block.block_type,
                "exercise_number": block.exercise_number,
                "example_number": block.example_number,
                "block_id": block.block_id,
                "neighboring_block_ids": list(block.neighboring_block_ids),
                "visual_refs": list(block.image_refs),
            }

            nodes.append(
                TextNode(
                    id_=str(uuid.uuid5(uuid.NAMESPACE_URL, block.block_id)),
                    text=content,
                    metadata=metadata,
                    excluded_embed_metadata_keys=["filename"],
                    excluded_llm_metadata_keys=["neighboring_block_ids"],
                )
            )

    return nodes


def clone_nodes(nodes: list[TextNode]) -> list[TextNode]:
    """Return fresh ``TextNode`` copies so the same parse can be embedded multiple times."""
    clones: list[TextNode] = []
    for node in nodes:
        clones.append(
            TextNode(
                id_=node.id_,
                text=node.get_content(),
                metadata=dict(node.metadata or {}),
                excluded_embed_metadata_keys=list(node.excluded_embed_metadata_keys),
                excluded_llm_metadata_keys=list(node.excluded_llm_metadata_keys),
            )
        )
    return clones
