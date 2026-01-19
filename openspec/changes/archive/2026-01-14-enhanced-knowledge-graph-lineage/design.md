# Technical Design: LLM-Assisted Knowledge Graph

## 1. Python-SQL Linker Design (`src/services/python_sql_llm_linker.py`)

### 1.1 Model Configuration
- **Model**: `mistralai/devstral-2512:free` (Strictly enforced 0-cost).
- **Service**: Usage via `OpenRouterService`.

### 1.2 Prompt Strategy
Devstral is a code model, so we will use a strict system prompt to enforce JSON output.

**System Prompt:**
```text
You are a static analysis tool for Python code.
Your task is to identify where SQL queries are executed against a database.
Analyze the provided Python code and extract:
1. The function name where execution happens.
2. The exact SQL query text (resolving f-strings or variables if possible).
3. The names of tables being READ or WRITTEN.

Output strictly valid JSON in this format:
[
  {
    "function_name": "process_data",
    "sql_text": "INSERT INTO target (a,b) VALUES (1,2)",
    "tables_read": [],
    "tables_written": ["target"],
    "confidence": 0.95
  }
]
If no SQL is found, return [].
```

**User Prompt:**
```text
Code to analyze:
{code_snippet}
```

### 1.3 Validation Logic
To prevent hallucinations, we apply deterministic checks on the LLM output:
1.  **Parse Check**: `sqlglot.transpile(link['sql_text'])`. If it fails, discard or mark `confidence=0.1`.
2.  **Table Existence**: If `tables_written` contains tables that exist in our Graph (Neo4j), boost confidence.

## 2. Integration into Ingestion Pipeline (`src/ingestion/ingestion_pipeline.py`)

### 2.1 Workflow
Inside `process_file(file_path)`:
1.  Identify file type. If `.py`:
2.  **Standard Parse**: Run `PythonPlugin` (existing) to get imports/functions.
3.  **LLM Linkage (NEW)**:
    -   Call `PythonSqlLLMLinker.analyze(file_content)`.
    -   Receive list of `DerivedSQLExecution` objects.
4.  **Graph Write**:
    -   Create `SQLQuery` nodes for the extracted SQL.
    -   Create `EXECUTES` edge from `PythonFile` (or Function) to `SQLQuery`.
    -   Create `READS/WRITES` edges from `SQLQuery` to `Table` nodes (using the `tables_read/written` from LLM *and* validated by `sqlglot`).

## 3. Knowledge Inference Service (`src/services/knowledge_inference.py`)

### 3.1 Orchestration
-   Iterate over all `Function` and `StoredProcedure` nodes in Neo4j (that lack `summary`).
-   Call `OpenRouterService` (using a cheap/fast model, potentially also Devstral or another free tier model if suitable for NL summary) to generate:
    -   `summary`: Natural language description.
    -   `logic_steps`: Bullet points of logic.
-   Write properties back to Neo4j.
-   **Vectorize**: Send `summary + logic_steps` to `QdrantService` to create embeddings.
