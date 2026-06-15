export interface EvalMetrics {
  hitAt1: number;
  hitAt3: number;
  hitAt5: number;
  mrr: number;
  avgContentMatch: number;
  avgLatencyMs: number;
}

export interface EvalCaseResult {
  caseId: string;
  queryType: string;
  label: string;
  bestRank: number | null;
  reciprocalRank: number;
  hitAt1: boolean;
  hitAt3: boolean;
  hitAt5: boolean;
  contentMatchRatio: number;
}

export interface EvalTarget {
  provider: string;
  model: string;
  collectionName: string;
  caseCount: number;
  metrics: EvalMetrics;
  cases: EvalCaseResult[];
}

export interface EvalFailure {
  provider: string;
  model: string;
  error: string;
}

export interface RetrievalEvalReport {
  schemaVersion: number;
  createdAt: string;
  goldenPath: string;
  topK: number;
  targets: EvalTarget[];
  failures: EvalFailure[];
}

const caseLabels = [
  ["goodfellow-ch2-001", "definition", "Scalars, vectors, matrices, tensors"],
  ["goodfellow-ch2-002", "definition", "Vector definition and indexing"],
  ["goodfellow-ch2-003", "definition", "Tensor axes and coordinates"],
  ["goodfellow-ch2-004", "figure", "Figure 2.1 transpose"],
  ["goodfellow-ch2-005", "concept", "Broadcasting vector addition"],
  ["goodfellow-ch2-006", "formula", "Matrix product dimensions"],
  ["goodfellow-ch2-007", "formula", "Matrix product summation"],
  ["goodfellow-ch2-008", "concept", "Multiplication properties"],
  ["goodfellow-ch2-009", "figure", "Figure 2.2 identity matrix"],
  ["goodfellow-ch2-010", "student_style", "Inverse as theoretical tool"],
  ["goodfellow-ch2-011", "definition", "Span of vectors"],
  ["goodfellow-ch2-012", "concept", "Linear dependence and solutions"],
  ["goodfellow-ch2-013", "formula", "Lp norm and norm properties"],
  ["goodfellow-ch2-014", "concept", "L1 norm sparsity proxy"],
  ["goodfellow-ch2-015", "definition", "Frobenius norm"],
  ["goodfellow-ch2-016", "concept", "Orthogonal matrix inverse"],
  ["goodfellow-ch2-017", "definition", "Eigenvector and eigenvalue"],
  ["goodfellow-ch2-018", "formula", "Symmetric eigendecomposition"],
  ["goodfellow-ch2-019", "definition", "Singular value decomposition"],
  ["goodfellow-ch2-020", "student_style", "PCA encoding"],
] as const;

type CompactCase = readonly [
  bestRank: number,
  reciprocalRank: number,
  contentMatchRatio: number,
];

function casesFrom(compact: readonly CompactCase[]): EvalCaseResult[] {
  return caseLabels.map(([caseId, queryType, label], index) => {
    const [bestRank, reciprocalRank, contentMatchRatio] = compact[index];
    return {
      caseId,
      queryType,
      label,
      bestRank,
      reciprocalRank,
      hitAt1: bestRank === 1,
      hitAt3: bestRank <= 3,
      hitAt5: bestRank <= 5,
      contentMatchRatio,
    };
  });
}

export const retrievalEvalReport = {
  schemaVersion: 1,
  createdAt: "20260615T234014Z",
  goldenPath: "evals/golden/goodfellow_ch2_retrieval.jsonl",
  topK: 5,
  targets: [
    {
      provider: "openai",
      model: "text-embedding-3-small",
      collectionName: "mathbird_openai_text_embedding_3_small",
      caseCount: 20,
      metrics: {
        hitAt1: 0.9,
        hitAt3: 1,
        hitAt5: 1,
        mrr: 0.9416666666666668,
        avgContentMatch: 0.7708333333333333,
        avgLatencyMs: 390.8487894979771,
      },
      cases: casesFrom([
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 0.5],
        [2, 0.5, 1],
        [1, 1, 0.6],
        [1, 1, 0.4],
        [1, 1, 1],
        [1, 1, 0.75],
        [1, 1, 1],
        [1, 1, 0.6],
        [1, 1, 0.6],
        [3, 0.3333333333333333, 0.2],
        [1, 1, 0.6666666666666666],
        [1, 1, 0.6666666666666666],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.8333333333333334],
      ]),
    },
    {
      provider: "openai",
      model: "text-embedding-3-large",
      collectionName: "mathbird_openai_text_embedding_3_large",
      caseCount: 20,
      metrics: {
        hitAt1: 0.9,
        hitAt3: 1,
        hitAt5: 1,
        mrr: 0.9333333333333332,
        avgContentMatch: 0.7791666666666668,
        avgLatencyMs: 365.2729334018659,
      },
      cases: casesFrom([
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 0.5],
        [1, 1, 1],
        [3, 0.3333333333333333, 0.6],
        [1, 1, 0.4],
        [1, 1, 1],
        [1, 1, 0.75],
        [3, 0.3333333333333333, 1],
        [1, 1, 0.4],
        [1, 1, 0.6],
        [1, 1, 0.4],
        [1, 1, 0.6666666666666666],
        [1, 1, 0.8333333333333334],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.8333333333333334],
      ]),
    },
    {
      provider: "cohere",
      model: "embed-english-v3.0",
      collectionName: "mathbird_cohere_embed_english_v3_0",
      caseCount: 20,
      metrics: {
        hitAt1: 0.9,
        hitAt3: 1,
        hitAt5: 1,
        mrr: 0.9416666666666668,
        avgContentMatch: 0.7058333333333333,
        avgLatencyMs: 174.4593749404885,
      },
      cases: casesFrom([
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 0.5],
        [1, 1, 0.2],
        [1, 1, 0.4],
        [1, 1, 0.6],
        [1, 1, 1],
        [1, 1, 0.75],
        [2, 0.5, 1],
        [1, 1, 0.4],
        [1, 1, 0.6],
        [3, 0.3333333333333333, 0.2],
        [1, 1, 0.6666666666666666],
        [1, 1, 0.5],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.5],
      ]),
    },
    {
      provider: "cohere",
      model: "embed-v4.0",
      collectionName: "mathbird_cohere_embed_v4_0",
      caseCount: 20,
      metrics: {
        hitAt1: 1,
        hitAt3: 1,
        hitAt5: 1,
        mrr: 1,
        avgContentMatch: 0.7891666666666668,
        avgLatencyMs: 212.900410455768,
      },
      cases: casesFrom([
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 0.5],
        [1, 1, 1],
        [1, 1, 0.6],
        [1, 1, 0.6],
        [1, 1, 1],
        [1, 1, 0.75],
        [1, 1, 1],
        [1, 1, 0.4],
        [1, 1, 0.6],
        [1, 1, 0.4],
        [1, 1, 0.6666666666666666],
        [1, 1, 0.8333333333333334],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.8333333333333334],
      ]),
    },
    {
      provider: "google",
      model: "gemini-embedding-001",
      collectionName: "mathbird_google_gemini_embedding_001",
      caseCount: 20,
      metrics: {
        hitAt1: 0.95,
        hitAt3: 1,
        hitAt5: 1,
        mrr: 0.975,
        avgContentMatch: 0.8025,
        avgLatencyMs: 288.2434397470206,
      },
      cases: casesFrom([
        [2, 0.5, 0.8],
        [1, 1, 0.8],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 0.5],
        [1, 1, 1],
        [1, 1, 0.6],
        [1, 1, 0.6],
        [1, 1, 1],
        [1, 1, 0.75],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.6],
        [1, 1, 0.8],
        [1, 1, 0.6666666666666666],
        [1, 1, 0.5],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.8333333333333334],
      ]),
    },
    {
      provider: "mistral",
      model: "mistral-embed",
      collectionName: "mathbird_mistral_mistral_embed",
      caseCount: 20,
      metrics: {
        hitAt1: 1,
        hitAt3: 1,
        hitAt5: 1,
        mrr: 1,
        avgContentMatch: 0.7991666666666667,
        avgLatencyMs: 402.82500630710274,
      },
      cases: casesFrom([
        [1, 1, 0.8],
        [1, 1, 0.8],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 1, 0.5],
        [1, 1, 1],
        [1, 1, 0.6],
        [1, 1, 0.6],
        [1, 1, 1],
        [1, 1, 0.75],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.6],
        [1, 1, 0.4],
        [1, 1, 0.6666666666666666],
        [1, 1, 0.8333333333333334],
        [1, 1, 1],
        [1, 1, 0.8],
        [1, 1, 0.8333333333333334],
      ]),
    },
  ],
  failures: [],
} satisfies RetrievalEvalReport;
