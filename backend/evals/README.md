# Evaluation Pipeline README

This document is the agent-facing map for Mathbird retrieval evaluation. Read it
before changing golden cases, embedding comparisons, chunking experiments,
evaluation scoring, or the frontend eval dashboard.

## What This Pipeline Evaluates

Mathbird lets a voice tutor answer questions about uploaded PDFs. The retrieval
eval pipeline measures whether RAG returns useful textbook evidence for a fixed
golden question set.

Current evaluation axes:

- **Embedding model comparison**: same parsed/indexed content, different
  embedding provider/model collections.
- **Chunking policy comparison**: same parser and embedding model, different
  node construction policies.
- **Structured lookup comparison**: same indexed collection, compares
  production `retrieve()`, structured Qdrant filters only, and semantic search
  only on page/section/figure/equation/example queries.

The pipeline is retrieval-only. It does not grade final LLM answers. The core
question is: "Did retrieval return the expected source pages and enough expected
content terms?"

## Important Files

Backend eval data and CLIs:

- `backend/evals/golden/goodfellow_ch2_retrieval.jsonl`
  - 40-case golden retrieval set for Goodfellow chapter 2.
- `backend/evals/golden/goodfellow_ch2_structured.jsonl`
  - 40-case golden set for structured lookup (page, section, figure, equation,
    example, chapter, mixed, and negative routing cases).
- `backend/evals/results/`
  - Timestamped JSON and Markdown reports produced by eval scripts.
- `backend/scripts/eval_retrieval.py`
  - Compares retrieval quality across embedding collections.
- `backend/scripts/eval_chunking.py`
  - Parses once, indexes multiple chunking policies, evaluates them, and can
    update the frontend dashboard JSON.
- `backend/scripts/eval_structured.py`
  - Evaluates structured lookup paths against the active Qdrant collection and
    can update the frontend dashboard JSON.

Backend RAG/eval internals:

- `backend/app/rag/evaluation.py`
  - Golden case loading, retrieval scoring, aggregate metrics, report
    serialization, Markdown rendering.
- `backend/app/rag/indexing.py`
  - Converts normalized parsed blocks into LlamaIndex `TextNode`s. Also owns the
    chunk policy registry used by chunking evals.
- `backend/app/rag/multi_ingest.py`
  - Parses a PDF once and indexes the same nodes into multiple embedding
    collections for embedding-model comparison.
- `backend/app/rag/llamaindex_qdrant.py`
  - Qdrant-backed retriever and index stack builder used by evals.
- `backend/app/rag/parsing.py`
  - Normalized parse models: `ParsedDocument`, `ParsedPage`, `ParsedBlock`,
    `RetrievedRecord`.
- `backend/app/rag/normalizer.py`
  - Converts LlamaParse output into page-aware textbook blocks.

Frontend dashboard:

- `frontend/src/data/embeddingEval.generated.json`
  - Generated embedding comparison report consumed by the dashboard.
- `frontend/src/data/chunkingEval.generated.json`
  - Generated chunking comparison report consumed by the dashboard.
- `frontend/src/data/structuredEval.generated.json`
  - Generated structured lookup comparison report consumed by the dashboard.
- `frontend/src/data/retrievalEval.ts`
  - Normalizes backend snake_case JSON into dashboard-friendly TypeScript types.
- `frontend/src/pages/EvalDashboardPage.tsx`
  - `/evals` dashboard page.
- `frontend/src/components/evals/`
  - Ranking table, case matrix, failure list, metric bars.

## Current Data Flow

### Embedding Comparison

Embedding comparison assumes the relevant Qdrant collections already exist.
Typical setup is:

1. Parse the source PDF once.
2. Convert parsed blocks into baseline nodes with `parsed_document_to_nodes`.
3. Insert cloned nodes into one Qdrant collection per embedding provider/model.
4. Run the golden set against each collection.
5. Write JSON/Markdown reports.
6. Optionally copy the JSON report into the frontend dashboard data file.

CLI:

```bash
cd backend
uv run python -m scripts.eval_retrieval \
  --golden evals/golden/goodfellow_ch2_retrieval.jsonl \
  --top-k 5 \
  --frontend-output ../frontend/src/data/embeddingEval.generated.json
```

To evaluate a subset:

```bash
cd backend
uv run python -m scripts.eval_retrieval \
  --target cohere:embed-v4.0 \
  --target mistral:mistral-embed \
  --top-k 5
```

Default embedding targets live in
`backend/app/rag/multi_ingest.py::DEFAULT_EMBEDDING_TARGETS`.

### Chunking Policy Comparison

Chunking comparison freezes parser, embedding provider/model, golden set, and
`top_k`. Only node construction varies.

Rebuild-and-evaluate data flow:

1. Parse the PDF once with LlamaParse.
2. For each chunk policy in `DEFAULT_CHUNK_POLICIES`, convert the same
   `ParsedDocument` into policy-specific nodes.
3. Insert each node set into a separate Qdrant collection.
4. Evaluate the same golden cases against each collection.
5. Write JSON/Markdown reports.
6. Optionally copy the JSON report into the frontend dashboard data file.

Use this when the PDF, parser, chunking policy implementation, embedding
provider, or embedding model changed:

```bash
cd backend
uv run python -m scripts.eval_chunking \
  --pdf ../materials/deep_learning_ian_goodfellow_chapter_2.pdf \
  --doc-id goodfellow-ch2 \
  --golden evals/golden/goodfellow_ch2_retrieval.jsonl \
  --provider cohere \
  --model embed-v4.0 \
  --top-k 5 \
  --frontend-output ../frontend/src/data/chunkingEval.generated.json
```

Evaluate-existing data flow:

1. Resolve each policy's existing Qdrant collection name.
2. Evaluate the golden cases against those collections.
3. Write JSON/Markdown reports.
4. Optionally copy the JSON report into the frontend dashboard data file.

Use this when only the golden set, scoring logic, `top_k`, or dashboard output
changed:

```bash
cd backend
uv run python -m scripts.eval_chunking \
  --golden evals/golden/goodfellow_ch2_retrieval.jsonl \
  --provider cohere \
  --model embed-v4.0 \
  --top-k 5 \
  --evaluate-existing \
  --frontend-output ../frontend/src/data/chunkingEval.generated.json
```

To evaluate a subset:

```bash
cd backend
uv run python -m scripts.eval_chunking \
  --evaluate-existing \
  --policy block \
  --policy page_section_window_512
```

### Structured Lookup Comparison

Structured lookup eval compares three retrieval paths against the **active**
settings collection (`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`,
`QDRANT_COLLECTION`):

1. `path:production` — full `retrieve()` (structured filter when applicable,
   semantic fallback otherwise).
2. `path:structured_only` — Qdrant payload filters only (no embedding).
3. `path:semantic_only` — vector search only.

**Re-ingest required:** structured cases depend on indexed metadata such as
`printed_page_number`, `section_number`, `figure_number`, and `equation_number`.
Re-index Goodfellow chapter 2 after metadata changes before running this eval.

CLI:

```bash
cd backend
uv run python -m scripts.eval_structured \
  --golden evals/golden/goodfellow_ch2_structured.jsonl \
  --top-k 5 \
  --frontend-output ../frontend/src/data/structuredEval.generated.json
```

Golden case format (structured JSONL):

```json
{
  "id": "goodfellow-ch2-s004",
  "doc_id": "goodfellow-ch2",
  "query": "section 2.7",
  "query_type": "structured_section",
  "expects_structured_route": true,
  "expected": {
    "printed_pages": [44],
    "must_contain": ["eigenvector"]
  },
  "golden_answer": "Section 2.7 defines eigendecomposition."
}
```

Per-case structured metrics in report JSON:

- `retrieval_path`: `structured`, `semantic`, or `structured_fallback_semantic`
- `routing_correct`: query parser routed as expected
- `structured_hit_at_1`: structured-only path Hit@1
- `structured_latency_ms` / `semantic_latency_ms`

## Built-In Chunk Policies

Chunk policies live in `backend/app/rag/indexing.py`.

### `block`

Current baseline. One `ParsedBlock` becomes one `TextNode`.

Use this as the control group. Keep baseline node IDs stable because existing
collections and tests expect deterministic block IDs.

### `block_neighbor_1`

One node per center block, but node text includes the center block plus one
same-page, same-section neighbor on each side.

This tests cheap local context expansion without whole-page noise.

### `page_section_window_512`

Packs adjacent blocks into windows within the same page and section, stopping at
roughly 512 whitespace tokens.

This tests whether formulas, definitions, and explanations work better when
nearby blocks are embedded together.

### `math_object_window`

Creates windows centered on math-heavy blocks:

- equation
- image
- graph
- table
- example
- exercise

Each node includes same-page, same-section nearby prose around the math object.
This targets formula, figure, example, and exercise questions.

## Golden Case Format

Golden cases are JSONL rows. Each row has one question and expected retrieval
evidence.

Required fields:

```json
{
  "id": "goodfellow-ch2-001",
  "doc_id": "goodfellow-ch2",
  "source_pdf": "materials/deep_learning_ian_goodfellow_chapter_2.pdf",
  "query": "What is the difference between scalars, vectors, matrices, and tensors?",
  "query_type": "definition",
  "expected": {
    "pages": [1, 2, 3],
    "printed_pages": [31, 32, 33],
    "section_titles": ["2.1 Scalars, Vectors, Matrices and Tensors"],
    "block_types": ["paragraph", "equation", "unknown"],
    "must_contain": ["scalar", "vector", "matrix", "tensor", "array"]
  },
  "notes": "Human context for maintainers.",
  "golden_answer": "Short answer for human inspection."
}
```

Scoring currently uses:

- `expected.pages` for page-hit matching.
- `expected.must_contain` for content coverage.
- `query_type` for failure analysis by category.
- `golden_answer` for report context and future answer-level evaluation.

`printed_pages`, `section_titles`, and `block_types` are preserved in report
JSON but are not all hard-scoring dimensions today.

## Metrics

Per target, `backend/app/rag/evaluation.py` reports:

- `hit_at_1`
- `hit_at_3`
- `hit_at_5`
- `mrr`
- `avg_content_match`
- `avg_latency_ms`

Per case:

- `best_rank`
- `best_score`
- `content_match_ratio`
- `matched_terms`
- `returned_sources`

Ranking sorts by:

1. `hit_at_3`
2. `mrr`
3. `hit_at_5`
4. lower latency

This favors reliable retrieval within the context window, then rank quality,
then speed.

## Report Schema

Generated reports use schema version `2`.

Top-level fields:

```json
{
  "schema_version": 2,
  "comparison_axis": "embedding_model",
  "created_at": "20260615T234014Z",
  "golden_path": "evals/golden/goodfellow_ch2_retrieval.jsonl",
  "top_k": 5,
  "targets": [],
  "failures": []
}
```

For chunking reports, `comparison_axis` is `chunk_policy`.

For structured lookup reports, `comparison_axis` is `structured_lookup`.

Each target includes:

```json
{
  "target_id": "chunk:block",
  "label": "Block",
  "comparison_axis": "chunk_policy",
  "metadata": {
    "chunk_policy": "block",
    "embedding_provider": "cohere",
    "embedding_model": "embed-v4.0",
    "node_count": 120
  },
  "provider": "cohere",
  "model": "embed-v4.0",
  "collection_name": "mathbird_chunk_block_cohere_embed_v4_0",
  "case_count": 40,
  "metrics": {},
  "cases": []
}
```

The frontend normalizer supports both backend snake_case and older camelCase
fixtures. Prefer backend snake_case in generated files.

## Frontend Dashboard Integration

The dashboard reads two generated report files:

```text
frontend/src/data/embeddingEval.generated.json
frontend/src/data/chunkingEval.generated.json
frontend/src/data/structuredEval.generated.json
```

To update `/evals`, write each eval axis to its matching generated file:

```bash
uv run python -m scripts.eval_retrieval \
  --frontend-output ../frontend/src/data/embeddingEval.generated.json

uv run python -m scripts.eval_chunking \
  --evaluate-existing \
  --frontend-output ../frontend/src/data/chunkingEval.generated.json

uv run python -m scripts.eval_structured \
  --frontend-output ../frontend/src/data/structuredEval.generated.json
```

The dashboard is intentionally generic:

- Embedding reports display model labels.
- Chunking reports display policy labels.
- Other future axes can work if they populate `target_id`, `label`,
  `comparison_axis`, and `metadata`, then get added to `retrievalEval.ts`.

After updating the generated JSON, run:

```bash
cd frontend
npm run lint
npm run build
```

## Adding A New Chunking Policy

1. Edit `backend/app/rag/indexing.py`.
2. Add a new `ChunkPolicyName` literal.
3. Add a `ChunkPolicy` entry to `DEFAULT_CHUNK_POLICIES`.
4. Implement a node builder function.
5. Add a branch in `parsed_document_to_chunked_nodes`.
6. Add focused tests in `backend/tests/rag/test_indexing.py`.
7. Run:

```bash
cd backend
uv run ruff check .
PYTHONPATH=. uv run pytest tests/rag/test_indexing.py -q
PYTHONPATH=. uv run pytest -q
```

Design rules:

- Keep `block` behavior backward-compatible.
- Preserve `doc_id`, `textbook_doc_id`, `page_number`, `section_title`,
  `chapter_number`, `block_type`, `block_id`, and visual metadata.
- Add `chunk_policy`, `chunk_id`, `chunk_kind`, `source_block_ids`, and
  `source_block_types` for every non-baseline policy.
- Do not call LlamaParse per policy. Parse once, transform many times.

## Adding A New Embedding Target

1. Make sure the provider exists in:
   - `backend/app/config.py::EmbeddingProvider`
   - `backend/app/rag/embeddings.py::build_embed_model`
2. Add the API key field to `Settings` if needed.
3. Add or override targets in `backend/app/rag/multi_ingest.py`.
4. Ingest nodes into the new collection.
5. Run `scripts.eval_retrieval`.

Do not import vendor SDKs outside provider boundary modules.

## Adding A New Golden Set

1. Add a new JSONL file under `backend/evals/golden/`.
2. Make sure every case has stable `id`, `doc_id`, `query`, expected `pages`,
   `must_contain`, and `golden_answer`.
3. Keep `doc_id` aligned with the document id used during ingestion.
4. Use `query_type` values that help failure analysis. Existing useful values:
   - `definition`
   - `formula`
   - `figure`
   - `concept`
   - `student_style`
5. Run evals with `--golden path/to/new.jsonl`.

If the new golden set uses a different PDF, pass matching `--pdf` and `--doc-id`
to `scripts.eval_chunking`.

## Environment Requirements

Common requirements:

- `uv sync --extra dev --dev` from `backend/`
- Qdrant running and reachable at `QDRANT_URL`
- Embedding provider API key for the chosen provider/model

Chunking eval additionally requires:

- `LLAMAPARSE_API_KEY`
- The source PDF path passed with `--pdf`

Local Qdrant usually runs at:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Do not commit `.env`. Tests that assert defaults should use
`Settings(_env_file=None)` or monkeypatch `get_settings` so local `.env` does
not leak into the assertion.

## Common Failure Modes

### `Collection not found`

The eval script is querying a collection that has not been indexed yet.

For embedding comparison, ingest the PDF into the target embedding collection
before running `eval_retrieval`.

For chunking comparison, `eval_chunking` indexes each policy collection itself
unless `--evaluate-existing` is set. With `--evaluate-existing`, the expected
policy collections must already exist. Check Qdrant connectivity, collection
names, and provider API keys.

### `LLAMAPARSE_API_KEY is required`

Only chunking eval parses the PDF directly. Set `LLAMAPARSE_API_KEY`.

### Cohere `429` trial key rate limit

Cohere trial keys are limited to 100 API calls per minute. The mitigation lives
in the embedding provider configuration, not the eval CLI. Keep these env vars
conservative when running chunking comparisons:

```dotenv
EMBEDDING_BATCH_SIZE=8
EMBEDDING_NUM_WORKERS=1
EMBEDDING_REQUESTS_PER_MINUTE=4
```

`EMBEDDING_BATCH_SIZE` reduces total API calls by sending larger batches where
the provider wrapper supports it, but keep it modest for Cohere trial keys
because chunk policies such as `block_neighbor_1` duplicate text into each
embedding input. `EMBEDDING_REQUESTS_PER_MINUTE` attaches a provider-level
sliding-window limiter so LlamaIndex does not fire every embedding batch at
once. If a run still fails, wait a minute and rerun only failed policies with
repeated `--policy` arguments.

### `top_k must be at least 5`

Golden scoring reports Hit@5, so eval scripts require `--top-k >= 5`.

### Dashboard still shows old results

The frontend reads `frontend/src/data/embeddingEval.generated.json`,
`frontend/src/data/chunkingEval.generated.json`, and
`frontend/src/data/structuredEval.generated.json`. Re-run the relevant eval
script with `--frontend-output` or replace the matching generated file
explicitly.

### Tests pass locally only with `PYTHONPATH=.`

From `backend/`, use:

```bash
PYTHONPATH=. uv run pytest -q
```

The project package is installed by uv, but this command is the known-good local
test invocation in this repo.

## Verification Commands

Backend:

```bash
cd backend
uv run ruff check .
PYTHONPATH=. uv run pytest -q
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Focused eval tests:

```bash
cd backend
PYTHONPATH=. uv run pytest \
  tests/rag/test_indexing.py \
  tests/rag/test_evaluation.py \
  tests/rag/test_eval_chunking.py \
  -q
```

## Agent Checklist For Future Eval Work

Before changing eval behavior:

1. Identify the axis: embedding model, chunking policy, parser, reranker, or
   answer-level scoring.
2. Freeze every variable except the axis under test.
3. Keep parser calls outside inner loops when possible.
4. Add/adjust focused tests before changing implementation.
5. Preserve report schema compatibility with the frontend normalizer.
6. Run backend lint and pytest.
7. If dashboard JSON or UI changed, run frontend lint/build.
8. Update this README and `docs/INDEX.md` when adding new eval files or major
   workflow changes.
