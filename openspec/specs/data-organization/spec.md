# data-organization Specification

## Purpose
TBD - created by archiving change structure-data-outputs. Update Purpose after archive.
## Requirements
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

### Requirement: Artifact Path Management

The system SHALL provide a centralized service for generating and resolving artifact paths.

#### Scenario: Generate artifact path
- **GIVEN** an ingestion run with ID "run_12345" for artifact type "sql_embeddings"
- **WHEN** the system requests an artifact path
- **THEN** the ArtifactManager SHALL return `data/{ProjectName}/{Timestamp}_{seq}_{action}/sql_embeddings/`
- **AND** the directory SHALL be created if it does not exist

#### Scenario: Resolve artifact path from run ID
- **GIVEN** a completed run with ID "run_12345"
- **WHEN** the system queries for artifacts by run ID
- **THEN** the ArtifactManager SHALL return the full path to the run directory
- **AND** include metadata about available artifact types

### Requirement: Legacy Data Migration

The system SHALL migrate existing flat-structure data to the new hierarchy.

#### Scenario: Archive root-level files
- **GIVEN** existing `.sql` files in the root `data/` directory
- **WHEN** migration is triggered
- **THEN** the system SHALL move files to `data/archive/{YYYYMMDD}/`
- **AND** preserve the original filenames
- **AND** log the migration action

#### Scenario: Preserve database file location
- **GIVEN** the migration process
- **WHEN** organizing data directory
- **THEN** the system SHALL keep `metadata.duckdb` in the root `data/` directory
- **AND** the system SHALL keep `contexts/` directory in the root `data/` directory
- **AND** no other files SHALL remain in the root except database and contexts

### Requirement: Integration with Ingestion Pipeline

The ingestion pipeline SHALL use the new directory structure for all artifacts.

#### Scenario: Ingest files to run directory
- **GIVEN** a file upload or GitHub ingestion request
- **WHEN** files are processed
- **THEN** the system SHALL save uploaded files to `{run_dir}/raw_source/`
- **AND** save generated embeddings to `{run_dir}/sql_embeddings/` or `{run_dir}/embeddings/`
- **AND** save any graph exports to `{run_dir}/graph_export/`

#### Scenario: Backward compatibility
- **GIVEN** existing code expects artifacts in specific locations
- **WHEN** the new structure is implemented
- **THEN** the system SHALL maintain backward compatibility through path resolution
- **AND** provide migration utilities for updating references

### Requirement: File Deduplication and Superseding

The system SHALL handle duplicate filenames by superseding older versions when the same file is re-ingested.

#### Scenario: Track latest file version per project
- **GIVEN** a file named "AdventureworksLT.sql" exists in project "AdventureworksLT"
- **WHEN** the same filename is uploaded again in a new ingestion run
- **THEN** the system SHALL store the new file in the new run directory
- **AND** mark the previous version as superseded in the database
- **AND** queries for "latest version" SHALL return the most recent run's file

#### Scenario: Preserve historical versions
- **GIVEN** multiple ingestion runs for the same project with duplicate filenames
- **WHEN** browsing run history
- **THEN** all historical versions SHALL remain accessible in their respective run directories
- **AND** each version SHALL be timestamped with its ingestion run

#### Scenario: Query latest file content
- **GIVEN** a project with multiple runs containing "schema.sql"
- **WHEN** the system needs to process the latest version
- **THEN** the file resolver SHALL return the file from the most recent run (highest timestamp)
- **AND** ignore older versions unless explicitly requested

#### Scenario: Prevent accidental duplicates
- **GIVEN** a concurrent ingestion uploads "data.sql"
- **WHEN** another ingestion for the same project uploads "data.sql" within the same second
- **THEN** the sequence number SHALL differentiate the runs
- **AND** both files SHALL be stored in separate run directories
- **AND** the version with higher sequence SHALL be considered newer

#### Scenario: Skip processing for identical content
- **GIVEN** a file "schema.sql" exists with SHA256 hash "abc123..."
- **WHEN** the same filename is uploaded with identical content (same hash)
- **THEN** the system SHALL detect the duplicate via hash comparison
- **AND** skip re-processing (embeddings, parsing, graph extraction)
- **AND** return a response indicating "content unchanged"
- **AND** set `skip_processing: true` in the registration result
- **AND** NOT mark the file as processed (preserve NULL `processed_at`)

### Requirement: Run Status Tracking

The system SHALL track run completion status with appropriate error handling.

#### Scenario: Run completion states
- **GIVEN** an ingestion run is created
- **WHEN** the run completes
- **THEN** the system SHALL set status to one of:
  - `"in_progress"` - Run currently executing
  - `"completed"` - All files processed successfully
  - `"completed_with_errors"` - Run finished but some files failed
  - `"failed"` - Run terminated with error
- **AND** record `completed_at` timestamp
- **AND** store error message if status is "completed_with_errors" or "failed"

#### Scenario: File processing completion
- **GIVEN** a file has been successfully processed (LLM extraction completed)
- **WHEN** marking the file as processed
- **THEN** the system SHALL set `processed_at` to current timestamp
- **AND** this timestamp SHALL be NULL for skipped duplicates

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

### Requirement: Embedding Artifact Capture
The system SHALL persist embedding payloads before upserting into Qdrant.

#### Scenario: Store embeddings payloads during indexing
- **WHEN** the ingestion pipeline prepares vectors for Qdrant upsert
- **THEN** the system SHALL write embedding artifacts under `/data/{project}/{run}/embeddings/`
- **AND** each record SHALL include the vector payload, metadata payload, and chunk index
- **AND** artifacts are written before the Qdrant upsert occurs

