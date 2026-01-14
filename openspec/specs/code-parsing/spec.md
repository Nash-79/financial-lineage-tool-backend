# code-parsing Specification

## Purpose
TBD - created by archiving change enhance-zero-cost-hybrid-lineage. Update Purpose after archive.
## Requirements
### Requirement: Plugin-Based Parser Architecture
The system SHALL support extensible code parsing through a plugin architecture that enables adding new languages without modifying core ingestion logic.

#### Scenario: Plugin registration
- **WHEN** system initializes
- **THEN** it loads parser plugins from `.env` configuration
- **AND** each plugin implements `LineagePlugin` interface
- **AND** plugins are registered by file extensions (e.g., `.sql`, `.py`, `.json`)

#### Scenario: Plugin interface compliance
- **WHEN** a new parser plugin is created
- **THEN** it MUST inherit from `LineagePlugin` abstract base class
- **AND** implement `supported_extensions() -> list[str]` property
- **AND** implement `parse(content: str, context: dict) -> LineageResult` method
- **AND** return standardized `LineageResult` with nodes, edges, external_refs

#### Scenario: Dynamic plugin loading
- **WHEN** ingestion pipeline processes a file
- **THEN** it selects parser plugin based on file extension
- **AND** if multiple plugins support the extension, uses first registered
- **AND** if no plugin matches, logs warning and skips file

#### Scenario: Plugin error isolation
- **WHEN** a parser plugin raises an exception
- **THEN** the error is caught and logged with plugin name
- **AND** file is marked as failed in ingestion logs
- **AND** other files continue processing (fail-isolated)

### Requirement: Standard SQL Parser Plugin
The system SHALL provide a standard SQL parser plugin using sqlglot for broad SQL dialect support.

#### Scenario: SQL plugin registration
- **WHEN** system loads plugins
- **THEN** `StandardSqlPlugin` is registered for extensions: `.sql`, `.ddl`, `.hql`
- **AND** plugin uses sqlglot library for parsing
- **AND** supports dialects: tsql, postgres, mysql, duckdb, spark, snowflake, fabric

#### Scenario: SQL parsing with plugin
- **WHEN** SQL file is ingested via plugin
- **THEN** plugin receives file content and context dict with `dialect` key
- **AND** uses sqlglot with specified dialect for parsing
- **AND** returns `LineageResult` with:
  - `nodes`: List of tables, views, functions, procedures
  - `edges`: READS_FROM, WRITES_TO, CALLS relationships
  - `external_refs`: Referenced tables not defined in file

#### Scenario: SQL plugin fallback
- **WHEN** sqlglot parsing fails (e.g., unsupported syntax)
- **THEN** plugin uses regex fallback parser
- **AND** logs warning about degraded parsing
- **AND** returns partial LineageResult with best-effort extraction

### Requirement: Python Parser Plugin with Tree-sitter
The system SHALL provide robust Python parsing using tree-sitter for syntax-error-tolerant analysis.

#### Scenario: Tree-sitter Python parsing
- **WHEN** Python file is ingested
- **THEN** `PythonTreesitterPlugin` is used for parsing
- **AND** plugin uses tree-sitter-python library
- **AND** handles partial/malformed files without crashing
- **AND** extracts:
  - Classes (name, bases, docstring, methods)
  - Functions (name, parameters, return type hints, docstring)
  - Imports (module names, from-imports)
  - SQL references in string literals (heuristic)

#### Scenario: Tree-sitter syntax error tolerance
- **WHEN** Python file contains syntax errors (e.g., incomplete code)
- **THEN** tree-sitter continues parsing valid portions
- **AND** returns partial AST with error nodes marked
- **AND** plugin extracts lineage from valid nodes only

#### Scenario: Python version compatibility
- **WHEN** parsing Python files with different syntax versions
- **THEN** tree-sitter handles Python 3.8 through 3.12 syntax
- **AND** recognizes type hints, walrus operators, pattern matching
- **AND** gracefully degrades for unsupported features

#### Scenario: Performance optimization with AST fallback
- **WHEN** Python file is small (<100 lines) and well-formed
- **THEN** plugin MAY use built-in `ast` module for faster parsing
- **AND** switches to tree-sitter only if `ast.parse()` fails
- **AND** decision is configurable via `PYTHON_PREFER_AST=true`

### Requirement: JSON Enrichment Plugin
The system SHALL provide a JSON parser plugin for metadata enrichment rather than standalone nodes.

#### Scenario: JSON parsing for enrichment
- **WHEN** JSON file is ingested (e.g., `table_metadata.json`)
- **THEN** `JsonEnricherPlugin` parses JSON structure
- **AND** extracts keys like `owner`, `sla`, `description`, `tags`
- **AND** returns `LineageResult` with enrichment properties (not standalone nodes)

#### Scenario: JSON enrichment application
- **WHEN** JSON enrichment result is processed
- **THEN** system looks up existing nodes by name heuristics
- **AND** applies JSON properties to matched nodes (e.g., `SET n.owner = 'Risk Team'`)
- **AND** does NOT create new nodes unless explicitly configured

### Requirement: Plugin Configuration
The system SHALL support plugin configuration via `.env` for easy extension.

#### Scenario: Plugin configuration via environment
- **WHEN** system loads plugin configuration from `.env`
- **THEN** `LINEAGE_PLUGINS` contains a comma-separated list of plugin module paths
- **AND** each plugin can have custom configuration parameters via `LINEAGE_PLUGIN_CONFIG_JSON`
- **AND** example structure:
  ```env
  LINEAGE_PLUGINS=src.ingestion.plugins.sql_standard.StandardSqlPlugin,src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin,src.ingestion.plugins.json_enricher.JsonEnricherPlugin
  LINEAGE_PLUGIN_CONFIG_JSON={"src.ingestion.plugins.sql_standard.StandardSqlPlugin":{"default_dialect":"duckdb"},"src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin":{"prefer_ast_for_small_files":true,"sql_extraction_enabled":true}}
  ```

#### Scenario: Disable plugin
- **WHEN** plugin is removed from `LINEAGE_PLUGINS`
- **THEN** system does not load that plugin
- **AND** files with matching extensions are skipped with warning
- **AND** no code changes required to disable parser

### Requirement: Plugin Result Standardization
The system SHALL enforce a standardized result format across all parser plugins.

#### Scenario: LineageResult structure
- **WHEN** any plugin returns parsing result
- **THEN** result MUST conform to `LineageResult` dataclass:
  ```python
  @dataclass
  class LineageResult:
      nodes: List[Node]           # Entities found in code
      edges: List[Edge]           # Relationships between entities
      external_refs: List[str]    # References to external entities
      metadata: dict              # Plugin-specific metadata
  ```

#### Scenario: Node standardization
- **WHEN** plugin creates a Node object
- **THEN** Node includes:
  - `name`: Unique identifier
  - `label`: Node type (DataAsset, Function, Class, etc.)
  - `type`: Subtype (Table, View, Procedure, etc.)
  - `properties`: Dict of additional attributes

#### Scenario: Edge standardization
- **WHEN** plugin creates an Edge object
- **THEN** Edge includes:
  - `source`: Source node name
  - `target`: Target node name
  - `relationship`: Type (READS_FROM, WRITES_TO, CALLS, DERIVES)
  - `properties`: Dict with confidence, source="parser", etc.

### Requirement: Plugin Testing
The system SHALL provide test harness for validating parser plugins.

#### Scenario: Plugin test suite
- **WHEN** new plugin is developed
- **THEN** plugin includes test suite with sample files
- **AND** tests verify `supported_extensions()` returns correct list
- **AND** tests verify `parse()` returns valid LineageResult
- **AND** tests cover error cases (syntax errors, empty files, huge files)

#### Scenario: Plugin regression tests
- **WHEN** plugin is modified
- **THEN** regression test suite runs against known sample files
- **AND** compares output LineageResult against golden snapshots
- **AND** CI fails if parser behavior regresses

