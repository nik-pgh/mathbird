"""LlamaIndex node construction for parsed textbook blocks and chunk policies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.rag.parsing import ParsedBlock, ParsedDocument

if TYPE_CHECKING:
    from llama_index.core.schema import TextNode

ChunkPolicyName = Literal[
    "block",
    "block_neighbor_1",
    "page_section_window_512",
    "math_object_window",
]

MATH_OBJECT_BLOCK_TYPES = frozenset({"equation", "image", "graph", "table", "example", "exercise"})


@dataclass(frozen=True)
class ChunkPolicy:
    name: ChunkPolicyName
    label: str
    description: str
    max_tokens: int = 512
    neighbor_radius: int = 0


DEFAULT_CHUNK_POLICIES: tuple[ChunkPolicy, ...] = (
    ChunkPolicy(
        name="block",
        label="Block",
        description="Current baseline: one normalized parser block per vector node.",
    ),
    ChunkPolicy(
        name="block_neighbor_1",
        label="Block + neighbors",
        description=(
            "One node per block, expanded with one same-page same-section neighbor "
            "on each side."
        ),
        neighbor_radius=1,
    ),
    ChunkPolicy(
        name="page_section_window_512",
        label="Page-section window",
        description=(
            "Adjacent same-page same-section blocks packed into windows up to "
            "about 512 tokens."
        ),
        max_tokens=512,
        neighbor_radius=1,
    ),
    ChunkPolicy(
        name="math_object_window",
        label="Math object window",
        description=(
            "Equation, figure, table, example, and exercise blocks centered "
            "with nearby prose."
        ),
        neighbor_radius=1,
    ),
)


def get_chunk_policy(name: str) -> ChunkPolicy:
    for policy in DEFAULT_CHUNK_POLICIES:
        if policy.name == name:
            return policy
    allowed = ", ".join(policy.name for policy in DEFAULT_CHUNK_POLICIES)
    raise ValueError(f"Unknown chunk policy {name!r}. Expected one of: {allowed}")


def _rough_token_count(text: str) -> int:
    return len(text.split())


def _block_content(block: ParsedBlock) -> str:
    return block.content_for_embedding().strip()


def _same_page_section(left: ParsedBlock, right: ParsedBlock) -> bool:
    return left.page_number == right.page_number and left.section_title == right.section_title


def _chunk_id(policy_name: str, blocks: list[ParsedBlock], *, suffix: str = "") -> str:
    first = blocks[0]
    last = blocks[-1]
    if first.block_id == last.block_id:
        base = first.block_id
    else:
        base = f"{first.block_id}..{last.block_id}"
    if policy_name == "block":
        return base
    return f"{policy_name}:{base}{suffix}"


def _primary_block(blocks: list[ParsedBlock]) -> ParsedBlock:
    for block in blocks:
        if block.block_type in MATH_OBJECT_BLOCK_TYPES:
            return block
    return blocks[0]


def _metadata(
    *,
    document: ParsedDocument,
    policy: ChunkPolicy,
    blocks: list[ParsedBlock],
    chunk_kind: str,
) -> dict[str, object]:
    primary = _primary_block(blocks)
    source_block_types = [block.block_type for block in blocks]
    return {
        "doc_id": document.doc_id,
        "textbook_doc_id": document.doc_id,
        "filename": document.filename,
        "page_number": primary.page_number,
        "printed_page_number": primary.printed_page_number or primary.page_number,
        "section_title": primary.section_title,
        "section_number": primary.section_number,
        "chapter_number": primary.chapter_number,
        "block_type": primary.block_type,
        "source_block_types": source_block_types,
        "exercise_number": primary.exercise_number,
        "example_number": primary.example_number,
        "figure_number": primary.figure_number,
        "equation_number": primary.equation_number,
        "block_id": primary.block_id,
        "chunk_id": _chunk_id(policy.name, blocks),
        "chunk_policy": policy.name,
        "chunk_policy_label": policy.label,
        "chunk_kind": chunk_kind,
        "chunk_token_count": _rough_token_count(
            "\n\n".join(_block_content(block) for block in blocks)
        ),
        "source_block_ids": [block.block_id for block in blocks],
        "neighboring_block_ids": list(primary.neighboring_block_ids),
        "visual_refs": [ref for block in blocks for ref in block.image_refs],
    }


def _node_from_blocks(
    document: ParsedDocument,
    policy: ChunkPolicy,
    blocks: list[ParsedBlock],
    *,
    chunk_kind: str,
    suffix: str = "",
) -> TextNode | None:
    from llama_index.core.schema import TextNode

    content = "\n\n".join(
        _block_content(block) for block in blocks if _block_content(block)
    ).strip()
    if not content:
        return None
    chunk_id = _chunk_id(policy.name, blocks, suffix=suffix)
    metadata = _metadata(document=document, policy=policy, blocks=blocks, chunk_kind=chunk_kind)
    metadata["chunk_id"] = chunk_id
    return TextNode(
        id_=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
        text=content,
        metadata=metadata,
        excluded_embed_metadata_keys=["filename"],
        excluded_llm_metadata_keys=["neighboring_block_ids"],
    )


def _all_blocks(document: ParsedDocument) -> list[ParsedBlock]:
    return [block for page in document.pages for block in page.blocks if _block_content(block)]


def _block_nodes(document: ParsedDocument, policy: ChunkPolicy) -> list[TextNode]:
    nodes: list[TextNode] = []
    for block in _all_blocks(document):
        node = _node_from_blocks(document, policy, [block], chunk_kind="block")
        if node is not None:
            nodes.append(node)
    return nodes


def _neighbor_blocks(blocks: list[ParsedBlock], index: int, radius: int) -> list[ParsedBlock]:
    center = blocks[index]
    start = index
    stop = index
    for candidate_index in range(index - 1, max(-1, index - radius - 1), -1):
        if _same_page_section(blocks[candidate_index], center):
            start = candidate_index
        else:
            break
    for candidate_index in range(index + 1, min(len(blocks), index + radius + 1)):
        if _same_page_section(blocks[candidate_index], center):
            stop = candidate_index
        else:
            break
    return blocks[start : stop + 1]


def _block_neighbor_nodes(document: ParsedDocument, policy: ChunkPolicy) -> list[TextNode]:
    blocks = _all_blocks(document)
    nodes: list[TextNode] = []
    for index, block in enumerate(blocks):
        node = _node_from_blocks(
            document,
            policy,
            _neighbor_blocks(blocks, index, policy.neighbor_radius),
            chunk_kind="block_neighbor",
            suffix=f":center:{block.block_id}",
        )
        if node is not None:
            node.metadata["block_id"] = block.block_id
            nodes.append(node)
    return nodes


def _page_section_window_nodes(document: ParsedDocument, policy: ChunkPolicy) -> list[TextNode]:
    nodes: list[TextNode] = []
    current: list[ParsedBlock] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            node = _node_from_blocks(document, policy, current, chunk_kind="page_section_window")
            if node is not None:
                nodes.append(node)
        current = []
        current_tokens = 0

    for block in _all_blocks(document):
        block_tokens = _rough_token_count(_block_content(block))
        if current and (
            not _same_page_section(current[-1], block)
            or current_tokens + block_tokens > policy.max_tokens
        ):
            flush()
        current.append(block)
        current_tokens += block_tokens
    flush()
    return nodes


def _math_object_window_nodes(document: ParsedDocument, policy: ChunkPolicy) -> list[TextNode]:
    blocks = _all_blocks(document)
    nodes: list[TextNode] = []
    seen_source_sets: set[tuple[str, ...]] = set()
    for index, block in enumerate(blocks):
        if block.block_type not in MATH_OBJECT_BLOCK_TYPES:
            continue
        window = _neighbor_blocks(blocks, index, policy.neighbor_radius)
        source_ids = tuple(item.block_id for item in window)
        if source_ids in seen_source_sets:
            continue
        seen_source_sets.add(source_ids)
        node = _node_from_blocks(
            document,
            policy,
            window,
            chunk_kind=f"{block.block_type}_window",
            suffix=f":center:{block.block_id}",
        )
        if node is not None:
            node.metadata["block_id"] = block.block_id
            node.metadata["block_type"] = block.block_type
            nodes.append(node)
    return nodes


def parsed_document_to_nodes(document: ParsedDocument) -> list[TextNode]:
    return parsed_document_to_chunked_nodes(document, policy_name="block")


def parsed_document_to_chunked_nodes(
    document: ParsedDocument,
    *,
    policy_name: ChunkPolicyName | str,
) -> list[TextNode]:
    policy = get_chunk_policy(policy_name)
    if policy.name == "block":
        return _block_nodes(document, policy)
    if policy.name == "block_neighbor_1":
        return _block_neighbor_nodes(document, policy)
    if policy.name == "page_section_window_512":
        return _page_section_window_nodes(document, policy)
    if policy.name == "math_object_window":
        return _math_object_window_nodes(document, policy)
    raise AssertionError(f"Unhandled chunk policy: {policy.name}")


def clone_nodes(nodes: list[TextNode]) -> list[TextNode]:
    """Return fresh ``TextNode`` copies so the same parse can be embedded multiple times."""
    from llama_index.core.schema import TextNode

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
