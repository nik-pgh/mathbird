import assert from "node:assert/strict";

// Mirror the production ordering: longest chunk-policy prefix wins.
const CHUNK_POLICIES = [
  "math_object_window_page_anchor",
  "page_section_window_512",
  "block_neighbor_1",
  "math_object_window",
  "block",
];

function extractChunkPolicy(collectionName) {
  if (!collectionName.startsWith("mathbird_chunk_")) {
    return null;
  }
  const rest = collectionName.slice("mathbird_chunk_".length);
  const policies = [...CHUNK_POLICIES].sort((a, b) => b.length - a.length);
  for (const policy of policies) {
    if (rest.startsWith(`${policy}_`)) {
      return policy;
    }
  }
  return null;
}

assert.equal(
  extractChunkPolicy(
    "mathbird_chunk_math_object_window_page_anchor_google_gemini_embedding_001",
  ),
  "math_object_window_page_anchor",
);
assert.equal(
  extractChunkPolicy("mathbird_chunk_math_object_window_google_gemini_embedding_001"),
  "math_object_window",
);
assert.equal(
  extractChunkPolicy("mathbird_chunk_block_neighbor_1_google_gemini_embedding_001"),
  "block_neighbor_1",
);

function extractCollectionVariant(collectionName, chunkPolicy) {
  if (!chunkPolicy) {
    return null;
  }
  const prefix = `mathbird_chunk_${chunkPolicy}_`;
  if (!collectionName.startsWith(prefix)) {
    return null;
  }
  const remainder = collectionName.slice(prefix.length);
  const match = remainder.match(/_v(\d+)$/);
  return match ? `v${match[1]}` : null;
}

assert.equal(
  extractCollectionVariant(
    "mathbird_chunk_math_object_window_page_anchor_google_gemini_embedding_001",
    "math_object_window_page_anchor",
  ),
  null,
);
assert.equal(
  extractCollectionVariant(
    "mathbird_chunk_math_object_window_page_anchor_google_gemini_embedding_001_v2",
    "math_object_window_page_anchor",
  ),
  "v2",
);

console.log("test-eval-catalog: ok");
