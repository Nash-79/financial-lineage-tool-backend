# LlamaIndex RAG Pipeline Documentation

Guide to the Retrieval-Augmented Generation (RAG) pipeline using LlamaIndex and local Ollama.

## Overview

The Financial Lineage Tool uses **LlamaIndex** with **local Ollama** for:
- 📝 Document indexing (SQL files, schemas)
- 🔍 Semantic search (vector similarity)
- 💬 Chat with RAG (context-aware responses)
- 📊 Knowledge graph integration

**Key Benefits:**
- ✅ **100% Local** - No cloud dependencies
- ✅ **Free** - No API costs
- ✅ **Private** - Data never leaves your machine
- ✅ **Fast** - Optimized with caching

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Chat Query                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  LlamaIndex     │
              │  Query Engine   │
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
   ┌───▼───┐      ┌───▼───┐      ┌───▼───┐
   │Qdrant │      │Ollama │      │Neo4j  │
   │Vector │      │ LLM   │      │Graph  │
   │Search │      │768-dim│      │ KB    │
   └───────┘      └───────┘      └───────┘
       │               │               │
   Embeddings    Generation      Entities
```

---

## Components

### 1. LlamaIndex Service

**File:** `src/llm/llamaindex_service.py`

**Responsibilities:**
- Initialize Ollama LLM and embeddings
- Connect to Qdrant vector store
- Create document indices
- Execute RAG queries
- Track metrics and caching

**Key Methods:**
```python
# Initialize
service = LlamaIndexService(
    ollama_host="http://localhost:11434",
    llm_model="llama3.1:8b",
    embedding_model="nomic-embed-text",
    qdrant_host="localhost",
    qdrant_port=6333
)

# Index documents
await service.index_documents(documents)

# Query with RAG
result = await service.query(
    question="What tables are in the schema?",
    similarity_top_k=5
)
```

### 2. Ollama Integration

**Models Used:**

| Model | Type | Size | Dimensions | Purpose |
|-------|------|------|------------|---------|
| `llama3.1:8b` | LLM | 4.7GB | - | Text generation |
| `nomic-embed-text` | Embeddings | 274MB | 768 | Vector search |

**Configuration:**
```bash
# Pull models (one-time)
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Verify
ollama list
```

### 3. Qdrant Vector Store

**Collection:** `code_chunks`
**Vector Size:** 768 dimensions
**Distance:** Cosine similarity

**Metadata Fields:**
- `file_path` - Source file
- `chunk_type` - Type (table, view, procedure, etc.)
- `tables` - Related tables
- `columns` - Column names
- `database` - Database name

### 4. Query Engine

**Modes:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `compact` | Concatenate chunks | Fast, simple queries |
| `tree_summarize` | Hierarchical summary | Complex analysis |
| `simple_summarize` | Single-pass summary | Quick overviews |

**Configuration:**
```python
query_engine = index.as_query_engine(
    similarity_top_k=5,      # Retrieve top 5 chunks
    response_mode="compact"   # Fast concatenation
)
```

---

## RAG Pipeline Flow

### Document Indexing

```
SQL File → Chunking → Embedding → Qdrant Storage
```

**Steps:**
1. **Load SQL file** - Read raw SQL content
2. **Semantic chunking** - Split by objects (tables, views, etc.)
3. **Create Documents** - Convert to LlamaIndex format
4. **Generate embeddings** - Ollama nomic-embed-text (768-dim)
5. **Store in Qdrant** - With metadata

**Code Example:**
```python
from llama_index.core import Document

# Create documents from SQL chunks
documents = [
    Document(
        text=chunk["content"],
        metadata={
            "file_path": chunk["file_path"],
            "chunk_type": "table",
            "tables": ["customers", "orders"],
            "database": "sales_db"
        }
    )
    for chunk in sql_chunks
]

# Index
await llamaindex_service.index_documents(documents)
```

### Query Execution

```
Query → Embedding → Vector Search → Context Retrieval → LLM Generation → Response
```

**Steps:**
1. **Embed query** - Convert to 768-dim vector
2. **Search Qdrant** - Find top-k similar chunks
3. **Retrieve context** - Get chunk text + metadata
4. **Construct prompt** - Combine query + context
5. **Generate response** - Ollama llama3.1:8b
6. **Return with sources** - Include citations

**Code Example:**
```python
result = await llamaindex_service.query(
    question="Show me the lineage of customer_id",
    similarity_top_k=5
)

print(result["response"])      # LLM-generated answer
print(result["sources"])       # Source chunks with metadata
print(result["query_latency_ms"])  # Performance metrics
```

---

## Chat Endpoints

### POST /api/chat/deep

**Deep analysis with maximum context**

```bash
curl -X POST http://localhost:8000/api/chat/deep \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze the complete lineage of customer_id from source to reporting"
  }'
```

**Features:**
- ✅ `similarity_top_k=10` (more context)
- ✅ Graph traversal integration
- ✅ Detailed source citations

### POST /api/chat/semantic

**Semantic search optimized**

```bash
curl -X POST http://localhost:8000/api/chat/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which tables contain customer data?"
  }'
```

**Features:**
- ✅ Configurable `SIMILARITY_TOP_K` (default 5)
- ✅ Fast vector search
- ✅ Natural language responses

### POST /api/chat/graph

**Graph-based queries**

```bash
curl -X POST http://localhost:8000/api/chat/graph \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show relationships between customers and orders tables"
  }'
```

**Features:**
- ✅ Neo4j graph context
- ✅ Entity relationship focus
- ✅ Cypher-aware responses

### POST /api/chat/text

**Simple text chat (no RAG)**

```bash
curl -X POST http://localhost:8000/api/chat/text \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is data lineage?"
  }'
```

**Features:**
- ✅ Direct LLM (no vector search)
- ✅ Fastest response time
- ✅ General knowledge queries

---

## Caching Strategy

### Embedding Cache (Redis)

**Key:** `sha256(text_content)`
**TTL:** 24 hours

```python
# Check cache
cache_key = f"embedding:{hashlib.sha256(text.encode()).hexdigest()}"
cached = await redis.get(cache_key)

if cached:
    return json.loads(cached)  # Cache hit

# Generate and cache
embedding = await ollama.embed(text)
await redis.setex(cache_key, 86400, json.dumps(embedding))
```

### Query Cache (Redis)

**Key:** `sha256(query + metadata_filters)`
**TTL:** 1 hour

```python
# Check cache
cache_key = f"query:{hashlib.sha256(query_data.encode()).hexdigest()}"
cached = await redis.get(cache_key)

if cached:
    metrics.query_cache_hits += 1
    return json.loads(cached)

# Execute and cache
result = await query_engine.aquery(query)
await redis.setex(cache_key, 3600, json.dumps(result))
```

---

## Metrics & Monitoring

### GET /api/v1/rag/status

**Response:**
```json
{
  "mode": "llamaindex",
  "total_queries": 150,
  "cache_hit_rate": 0.67,
  "avg_latency_ms": 450.5,
  "status": "healthy"
}
```

**Metrics Tracked:**
- `total_queries` - Total RAG queries processed
- `embedding_cache_hits/misses` - Embedding cache efficiency
- `query_cache_hits/misses` - Query cache efficiency
- `avg_query_latency_ms` - Average query time
- `avg_retrieval_latency_ms` - Vector search time
- `avg_generation_latency_ms` - LLM generation time

---

## Feature Flag

**Environment Variable:** `USE_LLAMAINDEX`

```bash
# Enable LlamaIndex RAG (default)
USE_LLAMAINDEX=true

# Use legacy RAG implementation
USE_LLAMAINDEX=false
```

**Code:**
```python
if config.USE_LLAMAINDEX and state.llamaindex_service:
    # Use LlamaIndex RAG
    result = await state.llamaindex_service.query(question)
else:
    # Use legacy Ollama + Qdrant direct
    result = await state.agent.query(question)
```

---

## Best Practices

### Document Indexing

✅ **DO:**
- Use semantic chunking for SQL (by object type)
- Include rich metadata (file, type, tables, columns)
- Batch index when possible
- Track indexing progress

❌ **DON'T:**
- Index very large files without chunking
- Skip metadata (reduces search quality)
- Re-index unchanged documents
- Ignore indexing errors

### Query Optimization

✅ **DO:**
- Use specific queries ("customer_id in orders table")
- Set appropriate `similarity_top_k` (5-10)
- Use metadata filters when possible
- Monitor cache hit rates

❌ **DON'T:**
- Use very broad queries ("tell me everything")
- Set `top_k` too high (>20 = slow)
- Ignore latency metrics
- Skip cache invalidation after re-indexing

---

## Troubleshooting

### Slow Queries

**Symptom:** Query latency >5 seconds

**Solutions:**
```bash
# Reduce top_k
SIMILARITY_TOP_K=3

# Use simpler response mode
RESPONSE_MODE=compact

# Check Ollama performance
time ollama run llama3.1:8b "test"

# Check Qdrant index size
curl http://localhost:6333/collections/code_chunks
```

### Poor Search Quality

**Symptom:** Irrelevant results returned

**Solutions:**
- ✅ Increase `similarity_top_k` to 10
- ✅ Use metadata filters
- ✅ Re-index with better chunking
- ✅ Check embedding model (must be nomic-embed-text)

### Ollama Connection Errors

**Symptom:** `Failed to connect to Ollama`

**Solutions:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check from Docker (if using containers)
docker compose exec api curl http://host.docker.internal:11434/api/tags

# Restart Ollama
# Windows: Restart Ollama service
# Unix: ollama serve
```

---

## Example Usage

### Full RAG Workflow

```python
# 1. Initialize service
from src.llm.llamaindex_service import LlamaIndexService

service = LlamaIndexService()

# 2. Check connectivity
await service.check_ollama_connectivity()

# 3. Index SQL files
from llama_index.core import Document

docs = [
    Document(
        text="CREATE TABLE customers (id INT, name VARCHAR(100))",
        metadata={"file_path": "schema.sql", "chunk_type": "table"}
    )
]

await service.index_documents(docs)

# 4. Query with RAG
result = await service.query(
    question="What columns are in the customers table?",
    similarity_top_k=5
)

print(f"Answer: {result['response']}")
print(f"Sources: {len(result['sources'])} chunks")
print(f"Latency: {result['query_latency_ms']:.2f}ms")

# 5. Check metrics
metrics = service.get_metrics()
print(f"Cache hit rate: {metrics['query_cache_hit_rate']:.2%}")
```

---

## Next Steps

- ✅ [Docker Setup](DOCKER_SETUP.md)
- ✅ [API Documentation](http://localhost:8000/docs)
- ✅ [Architecture Overview](ARCHITECTURE.md)
