# data-organization Spec Deltas

## ADDED Requirements

### Requirement: Embedding Artifact Capture
The system SHALL persist embedding payloads before upserting into Qdrant.

#### Scenario: Store embeddings payloads during indexing
- **WHEN** the ingestion pipeline prepares vectors for Qdrant upsert
- **THEN** the system SHALL write embedding artifacts under `/data/{project}/{run}/embeddings/`
- **AND** each record SHALL include the vector payload, metadata payload, and chunk index
- **AND** artifacts are written before the Qdrant upsert occurs

## MODIFIED Requirements

### Requirement: Hierarchical Data Storage

The system SHALL organize data artifacts in a project-based hierarchical directory structure.

#### Scenario: Create run directory on ingestion
- **GIVEN** a new ingestion starts for project "AdventureworksLT"
- **WHEN** the ingestion begins
- **THEN** the system SHALL create a timestamped run directory at `data/{ProjectName}/{Timestamp}_{seq}_{action}/`
- **AND** the timestamp SHALL use format `YYYYMMDD_HHmmss`
- **AND** the sequence number SHALL auto-increment for concurrent runs

#### Scenario: Store artifacts by type
- **GIVEN** an active ingestion run
- **WHEN** artifacts are generated (SQL chunks, embeddings, graph exports, raw files)
- **THEN** the system SHALL store each artifact type in its designated subdirectory:
  - Raw source files -> `raw_source/`
  - SQL embeddings -> `sql_embeddings/`
  - General embeddings -> `embeddings/`
  - Graph exports -> `graph_export/`
  - Code chunks -> `chunks/`
  - Validation outputs -> `validations/`
  - Neo4j snapshots -> `KG/`

#### Scenario: Preserve chronological order
- **GIVEN** multiple ingestion runs for the same project
- **WHEN** directories are listed
- **THEN** run folders SHALL be ordered chronologically by their timestamp prefix
- **AND** the directory listing SHALL clearly show the sequence of ingestion actions

### Requirement: Database Schema Enhancement

The system SHALL include file size tracking and DuckDB macros for business logic.

#### Scenario: File size tracking
- **GIVEN** a file is registered in the database
- **WHEN** computing file metadata
- **THEN** the system SHALL store `file_size_bytes` as BIGINT
- **AND** use file size for quick validation before hash computation

#### Scenario: DuckDB macros for business logic
- **GIVEN** the database schema is initialized
- **WHEN** creating tables for runs and files
- **THEN** the system SHALL create the following DuckDB macros:
  - `get_next_sequence(proj_id, ts)` - Returns next sequence number for concurrent runs
  - `find_duplicate_file(proj_id, repo_id, rel_path, fhash)` - Finds duplicate by hash
  - `find_previous_file_version(proj_id, repo_id, rel_path)` - Finds previous version for superseding
- **AND** these macros SHALL be used by the application layer
- **AND** centralize business logic in the database
