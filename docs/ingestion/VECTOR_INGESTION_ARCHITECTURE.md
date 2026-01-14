# Vector Ingestion Architecture

This document describes the vector (semantic search) track that chunks source
files and indexes them into Qdrant for retrieval.

## 1. Purpose

Code search needs stable, semantic boundaries. The ingestion pipeline therefore:

- Splits by logical object (table/view/procedure/function/class) whenever possible.
- Preserves enough context to answer lineage questions.
- Stores vector artifacts per ingestion run for auditability.

## 2. Chunking (`SemanticChunker`)

The chunker lives in `src/ingestion/semantic_chunker.py`.

### 2.1 SQL strategy (preferred)

- **Primary**: `sqlglot` AST parsing for statements, CTEs, and subqueries.
- **Fallback**: Domain-aware regex when parsing fails (e.g., `GO`, vendor syntax).
- **Dialect**: Set from ingestion request (`dialect`), defaulting to `auto`.

### 2.2 Python strategy

- Uses the Python `ast` module to extract functions, classes, and module blocks.
- Captures decorators and docstrings to preserve meaning.

### 2.3 Generic fallback

If a language is unknown or parsing fails, the chunker falls back to token-based
splitting with size caps to avoid oversized chunks.

## 3. Chunk artifacts (run-scoped)

Chunks are saved to disk for inspection before vectorization:

```
data/{project}/{run}/chunks/{source_stem}/{OBJECT_TYPE}/{OBJECT_NAME}.sql
```

Example:

```
data/InvestmentData/20260113_174506_001_ingest_postgres_investments/chunks/
  postgres_investments/TABLE/raw_market.trade_feed_venue_a.sql
```

## 4. Embedding pipeline

There are two modes:

### 4.1 LlamaIndex mode (`USE_LLAMAINDEX=true`)

- `LlamaIndexService.index_code_chunks(...)` handles embeddings and Qdrant writes.
- Uses the configured embedding model (defaults to `nomic-embed-text`).
- No local JSONL artifact is written in this mode today.

### 4.2 Legacy mode (direct Ollama + Qdrant)

- Uses `OllamaClient.embed` for each chunk.
- Writes an embeddings audit file when `embeddings_output_dir` is provided:

```
data/{project}/{run}/embeddings/{safe_file_name}_embeddings.jsonl
```

Each JSONL record includes the vector id, payload metadata, and vector payload.

## 5. Qdrant storage

Collection: `code_chunks` (cosine distance, 768-dim by default).

Payload fields include:

- `content`: raw chunk text
- `file_path`: absolute or repo-relative path
- `chunk_type`: semantic type (TABLE, VIEW, PROCEDURE, PYTHON_FUNCTION, ...)
- `tables`: referenced tables (if detected)
- `columns`: referenced columns (if detected)
- `language`: detected language
- `project_id`, `repository_id`, `source`: scoping metadata

Point ids are deterministic hashes of `(file_path, chunk_index)` in legacy mode.

## 6. Flow diagram

```mermaid
graph LR
    File(Source File) --> Chunker{SemanticChunker}

    subgraph Chunking
        Chunker -->|AST| AST[sqlglot / ast]
        Chunker -->|Fallback| Regex[Regex / Token Split]
        AST --> Chunk[Code Chunk]
        Regex --> Chunk
    end

    subgraph Vectorization
        Chunk --> Embed[Embedding Model]
        Embed --> Vector[Dense (and optional sparse) vectors]
    end

    subgraph Storage
        Vector --> Qdrant[(Qdrant)]
        Chunk --> ChunksDir[Run-scoped chunks/]
    end
```
