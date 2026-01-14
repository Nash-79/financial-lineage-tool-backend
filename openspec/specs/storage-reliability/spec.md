# Storage Reliability Specification

## Purpose
Define requirements for data storage reliability and robustness, including initialization retry logic and error handling to ensure system stability in variable environments.
## Requirements
### Requirement: Robust Database Initialization

The system SHALL initialize the metadata database robustly despite transient locking issues.

#### Scenario: Retry on lock failure
- **GIVEN** a database file is temporarily locked by another process
- **WHEN** the system attempts to initialize the database connection
- **THEN** it SHALL retry the connection multiple times (e.g., 5 attempts)
- **AND** wait between attempts (e.g., 1s backoff)
- **AND** only fail if all retry attempts are exhausted

#### Scenario: Log warnings
- **GIVEN** an initialization attempt fails
- **WHEN** the system retries
- **THEN** it SHALL log a warning with the error details and attempt count
- **AND** log a final error if all attempts fail

### Requirement: Idempotent File Ingestion
The system SHALL ensure that re-ingesting a file produces a clean slate state without stale nodes, edges, or vector chunks.

#### Scenario: Vector cleanup before ingestion
- **WHEN** a file is re-ingested into the system
- **THEN** the system SHALL delete all existing vector chunks for that file path
- **AND** deletion completes before new chunks are inserted
- **AND** no orphaned chunks remain in Qdrant

#### Scenario: Graph cleanup before ingestion
- **WHEN** a file is re-ingested
- **THEN** the system SHALL delete the File node and all related entities (DataAssets, Functions, Columns)
- **AND** deletion uses `DETACH DELETE` to remove relationships
- **AND** no orphaned nodes remain in Neo4j

#### Scenario: Purge-then-write pattern
- **WHEN** ingestion pipeline processes a file
- **THEN** it executes in order:
  1. Purge existing Qdrant chunks for file_path
  2. Purge existing Neo4j nodes for file_path
  3. Parse and chunk the file
  4. Insert new chunks and nodes
- **AND** failures in purge prevent insertion
- **AND** partial state is avoided

#### Scenario: File shrinkage handling
- **GIVEN** a file originally had 10 chunks and now has 5 chunks
- **WHEN** the file is re-ingested
- **THEN** all 10 old chunks are deleted
- **AND** exactly 5 new chunks are inserted
- **AND** no ghost chunks remain

### Requirement: Delete by File Path
The system SHALL support deletion of all data associated with a file path across all storage layers.

#### Scenario: Qdrant delete by file path
- **WHEN** `delete_by_file_path(collection, file_path)` is called
- **THEN** Qdrant deletes all points where `payload.file_path == file_path`
- **AND** deletion uses filter-based delete (not point IDs)
- **AND** returns count of deleted points

#### Scenario: Neo4j delete by file path
- **WHEN** `purge_file_assets(file_path)` is called
- **THEN** Neo4j executes Cypher:
  ```cypher
  MATCH (f:File {path: $file_path})
  OPTIONAL MATCH (f)<-[:DEFINED_IN]-(nodes)
  DETACH DELETE f, nodes
  ```
- **AND** returns count of deleted nodes

#### Scenario: Graceful failure handling
- **WHEN** deletion fails (e.g., Qdrant unavailable)
- **THEN** system logs error with file_path and exception
- **AND** raises exception to prevent partial ingestion
- **AND** ingestion pipeline retries or aborts based on configuration

### Requirement: Idempotency Verification
The system SHALL provide mechanisms to verify idempotent behavior of ingestion.

#### Scenario: Test corpus idempotency
- **GIVEN** a test file is ingested twice without modification
- **WHEN** comparing graph and vector state after both ingestions
- **THEN** node count, edge count, and chunk count are identical
- **AND** node IDs and edge relationships are identical
- **AND** vector payloads and embeddings are identical

#### Scenario: Idempotency metrics
- **WHEN** re-ingestion completes
- **THEN** system logs:
  - Chunks deleted from Qdrant
  - Nodes deleted from Neo4j
  - New chunks inserted
  - New nodes created
- **AND** metrics are exposed via `/api/v1/admin/ingestion-logs`

### Requirement: Post-Ingestion Validation
The system SHALL run a validation agent after ingestion to confirm parsing correctness and detect gaps.

#### Scenario: Validation agent execution
- **WHEN** ingestion completes for a file
- **THEN** validation agent runs against parsed output and graph state
- **AND** it detects missing nodes/edges relative to parsed results
- **AND** it emits a structured validation summary (pass/fail, gaps)

#### Scenario: Validation logging
- **WHEN** validation agent completes
- **THEN** validation output is attached to ingestion logs
- **AND** log entry includes file_path, gap counts, and validation status

### Requirement: Artifact Consistency Cleanup
The system SHALL validate ingestion artifacts and purge graph/vector data when required artifacts are missing.

#### Scenario: Missing artifacts trigger cleanup
- **WHEN** ingestion completes but required artifacts are missing for the file
- **THEN** the system SHALL purge Neo4j nodes and Qdrant chunks for the file
- **AND** the ingestion session is marked completed_with_errors
- **AND** ingestion logs record the missing artifact types

#### Scenario: Required artifact set
- **WHEN** ingestion finishes successfully
- **THEN** the system SHALL verify presence of the raw source file under the run directory
- **AND** the system SHALL verify chunk outputs under `/data/{project}/{run}/chunks/`
- **AND** the system SHALL verify validation output when the validation agent is enabled

### Requirement: Pre-Ingestion Neo4j Snapshot
The system SHALL capture a project/file-scoped Neo4j snapshot before ingestion for audit and comparison.

#### Scenario: Snapshot creation
- **WHEN** ingestion begins for a file or batch
- **THEN** system exports nodes and relationships scoped to the project and file paths
- **AND** artifact is stored under `/data/{project}/{run}/KG/`
- **AND** export completes before new nodes/edges are written

#### Scenario: Snapshot logging
- **WHEN** snapshot is created
- **THEN** ingestion logs include snapshot path and metadata (node/edge counts)

#### Scenario: Snapshot contents
- **WHEN** snapshot is written
- **THEN** it includes:
  - `metadata`: project name, project_id, run_id, ingestion_id, file_paths, timestamp, node_count, edge_count
  - `nodes`: id, labels, properties
  - `edges`: source_id, target_id, type, properties

### Requirement: Post-Ingestion Neo4j Snapshot
The system SHALL capture a project/file-scoped Neo4j snapshot after parsing completes to record the newly ingested graph state.

#### Scenario: Post-ingestion snapshot creation
- **WHEN** parsing completes for a file
- **THEN** the system SHALL export a Neo4j snapshot scoped to the project and file paths
- **AND** the snapshot is stored under `/data/{project}/{run}/KG/`
- **AND** ingestion logs include the post-ingestion snapshot path and node/edge counts

