"""Frontend output paths for structured lookup eval reports."""

from __future__ import annotations

from pathlib import Path

# Keep in sync with frontend CHUNK_POLICIES / CHUNK_POLICY_FRONTEND_SLUGS.
CHUNK_POLICY_NAMES: tuple[str, ...] = (
    "math_object_window_page_anchor",
    "page_section_window_512",
    "block_neighbor_1",
    "math_object_window",
    "block",
)

CHUNK_POLICY_FRONTEND_SLUGS: dict[str, str] = {
    "block": "block",
    "block_neighbor_1": "blockNeighbor",
    "page_section_window_512": "pageSectionWindow512",
    "math_object_window": "mathObjectWindow",
    "math_object_window_page_anchor": "mathObjectWindowPageAnchor",
}


def extract_chunk_policy_from_collection(collection_name: str) -> str | None:
    if not collection_name.startswith("mathbird_chunk_"):
        return None
    rest = collection_name[len("mathbird_chunk_") :]
    for policy in sorted(CHUNK_POLICY_NAMES, key=len, reverse=True):
        if rest.startswith(f"{policy}_"):
            return policy
    return None


def structured_eval_frontend_filename(chunk_policy: str) -> str:
    slug = CHUNK_POLICY_FRONTEND_SLUGS.get(chunk_policy, chunk_policy)
    return f"structuredEval.{slug}.generated.json"


def structured_eval_frontend_path(frontend_dir: Path, chunk_policy: str) -> Path:
    return frontend_dir / structured_eval_frontend_filename(chunk_policy)
