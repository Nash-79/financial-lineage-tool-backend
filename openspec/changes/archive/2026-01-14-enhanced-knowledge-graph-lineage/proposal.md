# OpenSpec Proposal: Enhanced Deep Knowledge Graph & Inference

## 1. Executive Summary
The goal is to transform the platform from a "File Lineage" tool into a "Deep Knowledge Graph" that captures granular semantics, business logic, and cross-system data flows.
This requires three pillars:
1.  **Deep Ingestion:** Recursively parsing SQL bodies (Procedures/MERGE) and tracing embedded SQL in Python.
2.  **Knowledge Inference:** Using LLMs to "read" code and generate summaries of logic, transformations, and column meanings.
3.  **Semantic Search:** leveraging Vector Embeddings (stored in **Qdrant**) of code + inference to enable natural language queries like "Show me PnL calculation".

## 2. Detailed Requirements

### 2.1 Deep Ingestion (Fixing Roots)
The current ingestion misses internal dependencies. We will implement:
-   **Generic SQL Support:** Extend `sql_standard.py` to parse `MERGE` statements (read/write) and `CREATE PROCEDURE` bodies (dependencies).
-   **Python-SQL Linking (LLM-Assisted):** A new `PythonSqlLinker` that uses `mistralai/devstral-2512:free` (via OpenRouter) to:
    -   Analyze Python code to identify SQL execution patterns (e.g., `cursor.execute(sql)`).
    -   Extract the constructed SQL text (handling variable resolution/f-strings).
    -   Identify the target tables and operation types.
    -   Pass the extracted SQL to the standard SQL parser for precise column-lineage.
    -   Creates explicit edges: `(PythonScript)-[:EXECUTES]->(SQLQuery)-[:WRITES_TO]->(Table)`.
-   **Column-Level Lineage:** Extract specific column names and types from `CREATE TABLE` and `SELECT` projection lists.

### 2.2 Semantic Enrichment (LLM Inference)
We will introduce a `KnowledgeInferenceService` step post-ingestion:
-   **Node Processing:** specific nodes (Functions, Procedures, Python Functions like `classify_risk`) are sent to the LLM.
-   **Inference Prompt:**
    ```text
    Analyze this code block:
    {code_content}
    1. Summarize the business purpose (e.g., "Calculates Daily PnL").
    2. Identify the core logic steps (e.g., "Normalizes trade side, subtracts start from end").
    3. List input/output columns with inferred types.
    ```
-   **Graph Update:** The inference result is stored as properties on the logical node in **Neo4j** (`summary`, `logic_desc`, `inferred_columns`).

### 2.3 Vectorization & Chunking strategy
Leveraging `src/ingestion/semantic_chunker.py` and `src/services/qdrant_service.py`:
-   **Chunking:** Use valid semantic boundaries (Functions, CTEs) instead of arbitrary text splitting.
-   **Embedding:** Generate vector embeddings for:
    -   The extraction **Summary** (high-level semantic search).
    -   The **Logic Description** (structural search).
    -   The **Raw Code** (syntax search).
-   **Storage:** Store vectors in **Qdrant** (Vector Index) attached to the corresponding nodes via ID.

## 3. Architecture Changes

### 3.1 Ingestion Layer
#### [MODIFY] `src/ingestion/plugins/sql_standard.py`
-   Add `exp.Merge` to `write_types`.
-   Implement recursive parsing for `CREATE PROCEDURE` bodies to extract internal dependencies (`READS_FROM`, `WRITES_TO`).
-   Refine regex fallbacks for Postgres `CREATE FUNCTION` bodies.

#### [NEW] `src/ingestion/python_sql_linker.py` (LLM-Powered)
-   Uses `OpenRouterService` to predict SQL executions within Python code.
-   Validates LLM-extracted SQL using `sqlglot` (sanity check).
-   Links Python functions to the Database Tables they touch.

### 3.2 Service Layer
#### [NEW] `src/services/knowledge_inference.py`
-   Orchestrates LLM calls to enrich graph nodes.
-   Manages "Re-inference" (only re-run if code hash changes).
-   Generates vectors for the *enriched summaries* and stores them in **Qdrant**.

### 3.3 API Layer
#### [NEW] `src/api/routers/database.py` (Enhancement)
-   `GET /api/v1/database/parsed-objects`: Returns hierarchical tree of ingested artifacts (Functions, Tables, Views).
-   `GET /api/v1/database/objects/{database}/{object_name}/dependencies`: Returns upstream/downstream lineage for a specific object.

## 4. Verification Plan (Deep Search Scenarios)

### Scenario 1: Cross-System Lineage
**Query:** "Show lineage for `PnLUsd` column."
**Expected Result:**
-   Graph Path: `core.FactDailyPnL (Column: PnLUsd)` <- `core.fn_CalcPnL (Function)` <- `daily_positions (View)` <- `etl_postgre_to_sql.py (Script)` <- `raw_market.trade_feed`.
-   *Success Criteria:* The path links Postgres Source -> Python ETL -> SQL Server Target.

### Scenario 2: Semantic Logic Search
**Query:** "Show me how PnL is calculated."
**Expected Result:**
-   Text Result: "PnL is calculated by function `core.fn_CalcPnL` using the formula `EndNotional - StartNotional`."
-   Graph Visualization: Highlights `core.fn_CalcPnL` and its input columns.
-   *Success Criteria:* LLM-generated summary is returned, not just raw code.

### Scenario 3: Python Transformation Logic
**Query:** "How are risk buckets assigned?"
**Expected Result:**
-   Finds Python function `classify_risk` in `etl_postgre_to_sql.py`.
-   Shows logic: "Rules based on asset_class, region, and notional_usd thresholds."
