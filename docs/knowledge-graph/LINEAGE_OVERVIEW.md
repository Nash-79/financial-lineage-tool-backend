# Lineage Overview

This overview explains how lineage is derived and stored in Neo4j today.

## 1. Deterministic lineage (baseline)

1. **Parse**: SQL, Python, and JSON are parsed into a normalized
   `LineageResult` (nodes + edges).
2. **Extract**: `GraphExtractor` batches node/edge writes into Neo4j.
3. **Scope**: Node ids are URN-based and scoped by `project_id` to keep
   projects isolated while preserving stable identifiers.

Deterministic edges are written with `source="parser"`, `confidence=1.0`,
and `status="approved"`.

## 2. LLM enrichment (post-ingestion)

After parsing, the KG enrichment agent may propose additional edges:

- Uses OpenRouter (free-tier model by default).
- Only connects nodes that already exist in the run-scoped context.
- Writes edges with `source="llm"` and `status="proposed"`.

This keeps deterministic lineage authoritative while capturing suggestions.

## 3. Query-time usage

Chat and lineage endpoints use `Neo4jGraphClient` to fetch:

- Entity matches (by name or id)
- Upstream/downstream paths
- Node/edge counts for summaries

For API details, see `../api/API_REFERENCE.md`.
