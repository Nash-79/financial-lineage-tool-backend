# Tasks: Enhanced Knowledge Graph

## 1. Deep Ingestion (Python & SQL)
- [x] 1.1 Update `sql_standard.py` to support `MERGE`.
- [x] 1.2 Implement recursive parsing for `CREATE PROCEDURE`.
- [x] 1.3 Implement `PythonSqlLLMLinker` using `OpenRouterService` (Devstral).
  - [x] Define prompt for SQL extraction.
  - [x] Implement validation logic (parse extracted SQL with `sqlglot`).
- [x] 1.4 Integrate linker into `ingestion_pipeline.py`.

## 2. Knowledge Inference Service
- [x] 2.1 Refactor/Extend `KGEnrichmentAgent` into `KnowledgeInferenceService`.
- [x] 2.2 Implement `infer_node_properties(code)` method using LLM.
- [x] 2.3 Store inference results (summary, logic) in Neo4j.

## 3. Vectorization & Search (Qdrant)
- [x] 3.1 Update `ingestion_pipeline.py` to embed inferred summaries into Qdrant.
- [x] 3.2 Ensure `qdrant_service.py` supports hybrid search on these new vectors.

## 4. API & Visualization
- [x] 4.1 Implement `GET /api/v1/database/parsed-objects` endpoint.
- [x] 4.2 Implement `GET /api/v1/database/objects/{db}/{name}/dependencies`.
