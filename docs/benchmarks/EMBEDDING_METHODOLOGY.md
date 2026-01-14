# Embedding Model Benchmarking Methodology

## Overview

This document describes the methodology for benchmarking embedding models in the Financial Lineage Tool RAG pipeline. The goal is to measure retrieval quality for SQL lineage queries and make data-driven decisions about embedding model selection.

---

## Why Benchmark Embeddings?

Embedding quality directly impacts RAG accuracy:

| Poor Embeddings → | Impact |
|-------------------|--------|
| Irrelevant chunks retrieved | LLM hallucinates answers |
| Relevant chunks missed | Incomplete lineage graphs |
| High latency | Poor user experience |

**Our Requirements:**
- **Precision@5 > 0.8** - Top results should be highly relevant
- **Recall@10 > 0.9** - Don't miss relevant code chunks
- **Latency < 100ms** - Fast enough for interactive queries
- **Ollama-compatible** - No API costs, runs locally

---

## Ground Truth Dataset

### Design Principles

1. **SQL-domain specific** - Generic text benchmarks (BEIR, MTEB) don't apply
2. **Realistic queries** - Actual questions users ask about lineage
3. **Diverse categories** - Cover different query types
4. **Manual verification** - Each relevant chunk verified by hand

### Dataset Structure

**Location**: `tests/benchmarks/embedding_ground_truth.json`

**Format**:
```json
{
  "queries": [
    {
      "id": "join_001",
      "query": "Which tables does customer_orders JOIN with?",
      "relevant_chunks": [
        "sql/analytics/customer_pipeline.sql",
        "sql/base/orders.sql"
      ],
      "category": "join_analysis",
      "difficulty": "easy"
    }
  ]
}
```

### Categories

| Category | Description | Count | Example |
|----------|-------------|-------|---------|
| **Join Analysis** | Multi-table dependencies | 5 | "Which tables does X JOIN with?" |
| **Schema Lookup** | Table/column discovery | 5 | "What columns are in users table?" |
| **Data Flow** | Upstream/downstream lineage | 5 | "What tables are upstream of X?" |
| **Transformation Logic** | CTEs, subqueries, aggregations | 7 | "Show me queries with window functions" |

**Total**: 22 queries

### Difficulty Levels

- **Easy** (30%) - Single table, direct match
- **Medium** (50%) - Multiple tables, semantic match
- **Hard** (20%) - Complex queries, requires deep understanding

---

## Metrics

### 1. Precision@k

**Definition**: Of the top k retrieved results, what fraction are relevant?

**Formula**:
```
Precision@k = (# relevant in top k) / k
```

**Interpretation**:
- `P@5 = 0.8` means 4 out of 5 top results are relevant
- Higher is better (max = 1.0)
- Measures **quality** of top results

**Target**: `P@5 > 0.8`

**Why it matters**: Users only look at top 5 results. If precision is low, they see irrelevant code → frustration.

---

### 2. Recall@k

**Definition**: Of all relevant chunks, what fraction appear in top k?

**Formula**:
```
Recall@k = (# relevant in top k) / (total # relevant)
```

**Interpretation**:
- `R@10 = 0.9` means 9 out of 10 relevant chunks found in top 10
- Higher is better (max = 1.0)
- Measures **coverage**

**Target**: `R@10 > 0.9`

**Why it matters**: Missing relevant code means incomplete lineage graphs.

---

### 3. Mean Reciprocal Rank (MRR)

**Definition**: Average position of the first relevant result.

**Formula**:
```
RR = 1 / (position of first relevant result)
MRR = average(RR) across all queries
```

**Interpretation**:
- `MRR = 0.7` means first relevant result typically at position 1.4
- Higher is better (max = 1.0)
- Measures **how quickly** you find a relevant result

**Target**: `MRR > 0.7`

**Why it matters**: Users expect the first result to be relevant.

---

### 4. Normalized Discounted Cumulative Gain (nDCG@k)

**Definition**: Ranking quality metric that rewards putting relevant results earlier.

**Formula**:
```
DCG@k = Σ (relevance_i / log2(i + 1)) for i in 1..k
IDCG@k = DCG for perfect ranking (all relevant first)
nDCG@k = DCG@k / IDCG@k
```

**Interpretation**:
- `nDCG@5 = 0.85` means ranking is 85% as good as perfect
- Higher is better (max = 1.0)
- Accounts for **position** - relevant result at #1 > relevant at #5

**Target**: `nDCG@5 > 0.85`

**Why it matters**: Not just about finding relevant chunks, but putting best ones first.

---

### 5. Latency

**Definition**: Average time to generate embeddings and search.

**Measurement**: Wall-clock time including:
- Query embedding generation
- Vector similarity search
- Result formatting

**Target**: `< 100ms average`

**Why it matters**: Interactive UI requires sub-200ms response time.

---

## Methodology

### Test Execution

1. **Load Ground Truth**: Parse `embedding_ground_truth.json`
2. **For each query**:
   - Embed query using test model
   - Search vector database for top-k chunks
   - Extract file paths from results
   - Calculate metrics (P@k, R@k, MRR, nDCG@k)
   - Measure latency
3. **Aggregate**: Average metrics across all queries
4. **Report**: Generate markdown with results and recommendation

### Path Matching

**Challenge**: Ground truth uses relative paths, search results may have full paths.

**Solution**: Fuzzy matching - check if ground truth path is substring of result.

```python
# Matches:
"sql/schema/users.sql" in "/repo/sql/schema/users.sql" → True

# Doesn't match:
"sql/schema/users.sql" in "sql/other.sql" → False
```

### Category Breakdown

Metrics are tracked per category to identify model strengths/weaknesses:

```python
results["by_category"] = {
  "join_analysis": {"precision_at_5": 0.82, "count": 5},
  "schema_lookup": {"precision_at_5": 0.90, "count": 5},
  ...
}
```

---

## Model Selection Criteria

### Decision Matrix

| Factor | Weight | Current (nomic-embed-text) | Candidate |
|--------|--------|----------------------------|-----------|
| Precision@5 | 40% | 0.82 | ? |
| Recall@10 | 30% | 0.91 | ? |
| Latency | 20% | 45ms | ? |
| Dimensions | 10% | 768 | ? |

**Calculation**:
```
Score = 0.4 * P@5 + 0.3 * R@10 + 0.2 * (1 - latency/200ms) + 0.1 * (1 - dims/1024)
```

### Trade-offs

**Quality vs Speed**:
- 2x better quality for 10x latency = ❌ Not worth it
- 10% better quality for 2x latency = ✅ Consider if quality critical

**Dimensions**:
- Higher dims (768, 1024) = better quality, slower, more storage
- Lower dims (384, 512) = faster, less storage, acceptable quality

**Rule of thumb**: 384-dim is sweet spot for SQL domain.

---

## Running Benchmarks

### Prerequisites

1. **Index test data**: Ingest sample SQL files
   ```bash
   python scripts/ingest_test_data.py
   ```

2. **Pull models**: Download all test models
   ```bash
   ollama pull nomic-embed-text
   ollama pull all-minilm-l6-v2
   ollama pull bge-small-en-v1.5
   ```

### CLI Usage

**List available models**:
```bash
python scripts/benchmark_embeddings.py --list-models
```

**Test single model**:
```bash
python scripts/benchmark_embeddings.py --model nomic-embed-text
```

**Compare all models**:
```bash
python scripts/benchmark_embeddings.py --compare-all
```

**Generate report from cached results**:
```bash
python scripts/benchmark_embeddings.py --report-only
```

### Output

- **Results JSON**: `docs/benchmarks/{model}_results.json`
- **Comparison Report**: `docs/benchmarks/embedding_comparison_YYYYMMDD.md`

---

## Interpreting Results

### Good Results

```
✅ Precision@5 > 0.8  → Top results highly relevant
✅ Recall@10 > 0.9    → Comprehensive coverage  
✅ MRR > 0.7          → First result usually relevant
✅ nDCG@5 > 0.85      → Good ranking quality
✅ Latency < 100ms    → Fast enough for UI
```

**Action**: ✅ Deploy model to production

### Mediocre Results

```
⚠️ Precision@5 = 0.6-0.8  → Some irrelevant results
⚠️ Recall@10 = 0.7-0.9    → Missing some chunks
⚠️ MRR = 0.5-0.7          → First result sometimes irrelevant
```

**Action**: 🔍 Investigate by category - is one query type weak?

### Poor Results

```
❌ Precision@5 < 0.6   → Too many irrelevant results
❌ Recall@10 < 0.7     → Missing critical chunks
❌ MRR < 0.5           → Relevant results buried
```

**Action**: ❌ Don't use this model - try alternatives

---

## Limitations

1. **Small dataset** (22 queries) - Not statistically significant
   - **Mitigation**: Expand to 50+ queries over time
   
2. **MockSearch** - Current implementation uses mock data
   - **Mitigation**: Replace with actual LlamaIndex search

3. **Binary relevance** - Doesn't account for degrees of relevance
   - **Mitigation**: Add graded relevance (0-2 scale) in future

4. **Static ground truth** - Doesn't evolve with codebase
   - **Mitigation**: Review quarterly, add new queries

---

## Future Improvements

1. **Automated ground truth generation** - Use LLM to suggest relevant chunks
2. **Cross-validation** - Split dataset into train/test sets
3. **A/B testing** - Compare models in production with real queries
4. **Fine-tuning** - Train custom embedding model on SQL domain
5. **Hybrid retrieval** - Combine dense (embeddings) + sparse (BM25)

---

## References

- [Information Retrieval Metrics (Manning et al.)](https://nlp.stanford.edu/IR-book/)
- [nDCG Explained](https://en.wikipedia.org/wiki/Discounted_cumulative_gain)
- [BEIR Benchmark](https://github.com/beir-cellar/beir) - General retrieval benchmark
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) - Embedding model rankings

---

## Questions?

For questions about this methodology, contact the maintainers or open an issue on GitHub.
