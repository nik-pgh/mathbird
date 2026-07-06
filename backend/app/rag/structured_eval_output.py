"""Frontend output paths for structured lookup eval reports."""

from __future__ import annotations

import re
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

_COLLECTION_VARIANT_RE = re.compile(r"_v(\d+)$")


def extract_chunk_policy_from_collection(collection_name: str) -> str | None:
    if not collection_name.startswith("mathbird_chunk_"):
        return None
    rest = collection_name[len("mathbird_chunk_") :]
    for policy in sorted(CHUNK_POLICY_NAMES, key=len, reverse=True):
        if rest.startswith(f"{policy}_"):
            return policy
    return None


def extract_collection_variant_slug(collection_name: str, chunk_policy: str) -> str | None:
    """Return a short variant label such as ``v2`` from a collection name tail."""
    prefix = f"mathbird_chunk_{chunk_policy}_"
    if not collection_name.startswith(prefix):
        return None
    remainder = collection_name[len(prefix) :]
    match = _COLLECTION_VARIANT_RE.search(remainder)
    if not match:
        return None
    return f"v{match.group(1)}"


def structured_eval_frontend_filename(
    chunk_policy: str,
    *,
    variant_slug: str | None = None,
) -> str:
    slug = CHUNK_POLICY_FRONTEND_SLUGS.get(chunk_policy, chunk_policy)
    if variant_slug:
        return f"structuredEval.{slug}.{variant_slug}.generated.json"
    return f"structuredEval.{slug}.generated.json"


def structured_eval_frontend_path(
    frontend_dir: Path,
    chunk_policy: str,
    *,
    collection_name: str | None = None,
) -> Path:
    variant_slug = None
    if collection_name:
        variant_slug = extract_collection_variant_slug(collection_name, chunk_policy)
    return frontend_dir / structured_eval_frontend_filename(
        chunk_policy,
        variant_slug=variant_slug,
    )
