# Knowledge Graph Architecture

This document describes the deterministic lineage graph in Neo4j and the
post-ingestion enrichment flow.

## 1. Core components

- `CodeParser` (`src/ingestion/code_parser.py`): parses SQL/Python/JSON.
- Lineage plugins (`src/ingestion/plugins/`): normalize parser output into a
  `LineageResult` (nodes, edges, external refs).
- `GraphExtractor` (`src/knowledge_graph/entity_extractor.py`): converts results
  into Neo4j nodes and relationships with batch writes.
- `Neo4jGraphClient` (`src/knowledge_graph/neo4j_client.py`): query and traversal
  utilities used by chat and lineage endpoints.

## 2. Node labels (current)

Common labels produced by the SQL plugin and extractor:

- `DataAsset` (base label for external or generic assets)
- `Table`, `View`, `MaterializedView`
- `Column`
- `Transformation`
- `FunctionOrProcedure`
- `Trigger`
- `Synonym`
- `File` (source file nodes when file ingestion is used)
- `JsonDocument`, `JsonKey` (JSON ingestion)

Each node stores `project_id`, `repository_id`, and `source_file` when available.

## 3. Relationship types (current)

Relationships are created from parser output and normalized plugin edges:

- `READS_FROM` (table/procedure reads another data asset)
- `DERIVES` (views/materialized views derived from sources)
- `CONTAINS` (asset contains column)
- `GENERATES` (transformation generates a target column)
- `INPUT_TO` (source column feeds a transformation)
- `CALLS` (object invokes another routine)
- `ATTACHED_TO` (trigger attached to target table)
- `ALIAS_OF` (synonym points to underlying asset)
- `CONTAINS_CONTENT` / `HAS_KEY` (JSON structural edges)

## 4. Edge metadata

All relationships include hybrid lineage metadata:

- `source`: origin of the edge (default `parser`)
- `confidence`: numeric score (default `1.0` for deterministic edges)
- `status`: lifecycle (`approved` for deterministic edges)
- `project_id`, `source_file`, `ingestion_id` (scope and traceability)

LLM-enriched edges use:

- `source="llm"`
- `status="proposed"`
- `model`, `reasoning`, `confidence` (as supplied by the KG agent)

## 5. KG enrichment (post-ingestion)

The enrichment agent (`src/services/kg_enrichment_agent.py`) runs after parsing:

1. Fetches context nodes scoped to `file_path` and `project_id`.
2. Calls OpenRouter (default `mistralai/devstral-2512:free`) to propose edges.
3. Writes accepted edges directly to Neo4j with `source="llm"` and `status="proposed"`.
4. Records a summary in ingestion logs.

## 6. Snapshots and run scope

For each ingestion run, Neo4j snapshots are written under:

```
data/{project}/{run}/KG/neo4j_snapshot_{phase}_{timestamp}_{ingestion_id}.json
```

Snapshots are filtered to the current project and file paths, keeping the
knowledge graph output run-scoped and reproducible.

## 7. Validation

The post-ingestion ValidationAgent compares parser output against Neo4j state
to detect missing nodes/edges. Validation artifacts are stored under:

```
data/{project}/{run}/validations/{file}_validation.json
```

These artifacts are logged in `ingestionLogs` for traceability.
