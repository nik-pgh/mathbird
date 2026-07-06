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

console.log("test-eval-catalog: ok");
