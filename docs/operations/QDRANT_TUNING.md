# Qdrant HNSW Index Tuning Guide

## Overview

This guide explains how to tune Qdrant's HNSW (Hierarchical Navigable Small World) index parameters for optimal performance in the Financial Lineage Tool. HNSW is the vector index algorithm that enables fast similarity search for RAG retrieval.

---

## What is HNSW?

**HNSW** is a graph-based approximate nearest neighbor (ANN) algorithm that:
- Builds a multi-layer graph structure for efficient search
- Trades perfect accuracy for speed (99%+ recall achievable)
- Configurable via two main parameters: `ef_construct` and `m`

**Use Case**: Powers vector similarity search for code chunk retrieval in RAG pipeline.

---

## Key Parameters

### 1. `ef_construct` (Exploration Factor at Construction)

**What it controls**: Search quality during index building.

**Range**: 4 to 1000+ (default: 100)

**Impact**:
- **Higher** → Better index quality, slower indexing, more memory
- **Lower** → Faster indexing, less memory, lower recall

**Recommendation**:
- **Small datasets** (<10k vectors): `ef_construct = 100` (default)
- **Medium datasets** (10k-100k): `ef_construct = 200`
- **Large datasets** (>100k): `ef_construct = 300-400`

**Configuration**:
```bash
# .env
QDRANT_HNSW_EF_CONSTRUCT=200
```

---

### 2. `m` (Number of Bi-Directional Links)

**What it controls**: Graph connectivity.

**Range**: 2 to 100+ (default: 16)

**Impact**:
- **Higher** → Better recall, more memory, slower indexing
- **Lower** → Less memory, faster indexing, lower recall

**Recommendation**:
- **Dimension < 384**: `m = 16` (default)
- **Dimension 384-768**: `m = 24`
- **Dimension > 768**: `m = 32`

**Configuration**:
```bash
# .env
QDRANT_HNSW_M=24
```

---

## Performance Trade-offs

### Memory Usage

```
Memory per vector ≈ m * dimensions * 4 bytes + overhead

Examples (for 768-dim vectors):
- m=16: ~50 KB per vector
- m=24: ~75 KB per vector
- m=32: ~100 KB per vector
```

**For 100k vectors**:
- m=16: ~5 GB RAM
- m=24: ~7.5 GB RAM
- m=32: ~10 GB RAM

### Indexing Speed

| ef_construct | m | 100k vectors | 1M vectors |
|--------------|---|--------------|------------|
| 100 | 16 | ~2 min | ~30 min |
| 200 | 24 | ~5 min | ~60 min |
| 400 | 32 | ~12 min | ~150 min |

### Search Quality vs Speed

**Recall** = % of true nearest neighbors found

| Configuration | Recall | Queries/sec |
|--------------|--------|-------------|
| ef=100, m=16 | 95% | 5000 |
| ef=200, m=24 | 98% | 3000 |
| ef=400, m=32 | 99.5% | 1500 |

---

## Recommended Configurations

### Development (Fast Iteration)

```bash
QDRANT_HNSW_EF_CONSTRUCT=100
QDRANT_HNSW_M=16
```

**Why**: Fast indexing, low memory, acceptable recall (95%+)

---

### Production (Balanced)

```bash
QDRANT_HNSW_EF_CONSTRUCT=200
QDRANT_HNSW_M=24
```

**Why**: Good recall (98%+), reasonable memory, production-grade

---

### Production (High Quality)

```bash
QDRANT_HNSW_EF_CONSTRUCT=400
QDRANT_HNSW_M=32
```

**Why**: Excellent recall (99.5%+), worth extra memory for critical applications

**When to use**: Financial data where missing a relevant SQL file is costly

---

## Implementation

### Code Integration

The Financial Lineage Tool already supports these parameters:

```python
# src/services/qdrant_service.py (user implemented)

from src.api.config import config

def create_collection(
    collection_name: str,
    vector_size: int,
    distance: str = "Cosine"
):
    hnsw_config = {
        "ef_construct": config.QDRANT_HNSW_EF_CONSTRUCT,
        "m": config.QDRANT_HNSW_M
    }
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "size": vector_size,
            "distance": distance
        },
        hnsw_config=hnsw_config
    )
```

### Configuration

Add to `.env` or environment:

```bash
# HNSW Index Parameters
QDRANT_HNSW_EF_CONSTRUCT=200  # Construction quality
QDRANT_HNSW_M=24               # Graph connectivity
```

### Verify Settings

```python
# Check current collection config
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
info = client.get_collection("code_chunks")

print(f"ef_construct: {info.config.hnsw_config.ef_construct}")
print(f"m: {info.config.hnsw_config.m}")
```

---

## Tuning Workflow

### Step 1: Baseline

Start with defaults:
```bash
ef_construct = 100
m = 16
```

Measure:
- Indexing time
- Memory usage
- Search recall (using embedding benchmark)

### Step 2: Increase Quality

If recall < 95%, increase `ef_construct`:
```bash
ef_construct = 200  # Try first
ef_construct = 300  # If still low
ef_construct = 400  # Maximum recommended
```

### Step 3: Adjust Connectivity

If recall still low, increase `m`:
```bash
m = 24  # For 384-768 dim
m = 32  # For >768 dim or critical applications
```

### Step 4: Validate

Run embedding benchmark:
```bash
python scripts/benchmark_embeddings.py --model nomic-embed-text
```

Check:
- Precision@5 > 0.8
- Recall@10 > 0.9
- Latency < 100ms

### Step 5: Monitor Production

Track metrics:
- Average query latency
- 95th percentile latency
- Memory usage
- False positives in retrieved chunks

---

## Common Issues

### Issue 1: Low Recall (<90%)

**Symptoms**: Missing relevant code chunks in RAG responses

**Solutions**:
1. Increase `ef_construct` to 200-400
2. Increase `m` to 24-32
3. Check embedding model quality (run embedding benchmark)

### Issue 2: High Memory Usage

**Symptoms**: Out of memory errors, slow performance

**Solutions**:
1. Decrease `m` (e.g., 32 → 24 → 16)
2. Use smaller embedding model (768-dim → 384-dim)
3. Shard collection across multiple Qdrant instances

### Issue 3: Slow Indexing

**Symptoms**: Takes hours to index codebase

**Solutions**:
1. Decrease `ef_construct` (e.g., 400 → 200 → 100)
2. Use batch embedding (already implemented in Financial Lineage Tool)
3. Index incrementally, not full reindex

### Issue 4: Slow Search

**Symptoms**: Queries take >200ms

**Solutions**:
1. Check `ef` parameter during search (not `ef_construct`)
2. Reduce top-k results
3. Ensure Qdrant has sufficient RAM (vectors should be in memory)

---

## Advanced: Search-Time Tuning

### `ef` (Exploration Factor at Search Time)

**Different from `ef_construct`** - controls search quality vs speed.

**Default**: `ef = top_k` (minimum)

**Recommendation**: `ef = top_k * 2` for better recall

**Configuration**:
```python
# During search
results = client.search(
    collection_name="code_chunks",
    query_vector=embedding,
    limit=10,
    search_params={"ef": 20}  # 2x top_k
)
```

**Trade-off**:
- `ef = 10` → Fastest, 90% recall
- `ef = 20` → Balanced, 95% recall
- `ef = 50` → Slow, 99% recall

---

## Monitoring

### Collection Statistics

```python
# Get collection info
info = client.get_collection("code_chunks")

print(f"Vectors: {info.vectors_count}")
print(f"Segments: {info.segments_count}")
print(f"Index: {info.indexed_vectors_count}")
print(f"HNSW ef_construct: {info.config.hnsw_config.ef_construct}")
print(f"HNSW m: {info.config.hnsw_config.m}")
```

### Search Performance

Track in OpenTelemetry:
- `qdrant_search_latency_ms` (histogram)
- `qdrant_search_results_count` (counter)
- `embedding_cache_hit_rate` (gauge)

---

## Best Practices

1. **Start conservative**: Use defaults, tune only if needed
2. **Measure first**: Run benchmarks before changing
3. **One parameter at a time**: Don't change both ef_construct and m simultaneously
4. **Monitor in production**: Track recall and latency
5. **Reindex when changing**: Parameters only apply to new collections

---

## References

- [Qdrant HNSW Documentation](https://qdrant.tech/documentation/guides/configuration/#hnsw-index)
- [HNSW Paper (Malkov & Yashunin)](https://arxiv.org/abs/1603.09320)
- [ANN Benchmarks](https://ann-benchmarks.com/) - Compare algorithms

---

## Quick Reference

| Scenario | ef_construct | m | Why |
|----------|--------------|---|-----|
| **Dev/Test** | 100 | 16 | Fast iteration |
| **Prod (Balanced)** | 200 | 24 | Good quality |
| **Prod (High Quality)** | 400 | 32 | Best recall |
| **Low Memory** | 100 | 8 | Minimal RAM |
| **Large Dataset** | 300 | 24 | Scale to millions |

**Rule of Thumb**: If in doubt, use production balanced (200, 24).

---

## Questions?

For questions about HNSW tuning, consult the Qdrant documentation or open an issue.
