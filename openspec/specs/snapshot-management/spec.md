# snapshot-management Specification

## Purpose
TBD - created by archiving change inmemory-duckdb-snapshots. Update Purpose after archive.
## Requirements
### Requirement: In-Memory DuckDB Operation
The system SHALL use DuckDB in-memory mode (`:memory:`) as the primary database for metadata storage instead of persistent file-based storage.

#### Scenario: Backend initializes with in-memory database
**Given** the backend container starts  
**When** the DuckDB client initializes  
**Then** it SHALL create an in-memory database connection  
**And** the database SHALL NOT create any `.duckdb` file locks

#### Scenario: In-memory database is faster than persistent
**Given** the system is using in-memory DuckDB  
**When** a query is executed  
**Then** the query response time SHALL be faster than file-based DuckDB  
**And** there SHALL be no file I/O wait time

---

### Requirement: Automatic Snapshot Creation
The system SHALL automatically create database snapshots to persistent storage when data changes are detected.

#### Scenario: Snapshot created when data changes
**Given** the background snapshot task is running  
**And** data has been added to the database since the last snapshot  
**When** the 5-minute check interval elapses  
**Then** the system SHALL create a new snapshot file  
**And** the snapshot filename SHALL include the current UTC timestamp in format `snapshot_YYYYMMDD_HHMMSS.duckdb`

#### Scenario: No snapshot created when data unchanged
**Given** the background snapshot task is running  
**And** no data has changed since the last snapshot  
**When** the 5-minute check interval elapses  
**Then** the system SHALL NOT create a new snapshot  
**And** disk space SHALL not be wasted on duplicate snapshots

#### Scenario: Snapshot created on graceful shutdown
**Given** the backend is running with in-memory database  
**And** the database contains data  
**When** the container receives a shutdown signal  
**Then** the system SHALL create a final snapshot before exiting  
**And** the snapshot SHALL be written to disk successfully

---

### Requirement: Snapshot Retention Policy
The system SHALL maintain only the 5 most recent snapshots and automatically delete older snapshots.

#### Scenario: Old snapshots are cleaned up
**Given** there are 6 snapshots in the snapshots directory  
**When** a new snapshot is created  
**Then** the system SHALL delete the oldest snapshot  
**And** exactly 5 snapshots SHALL remain  
**And** the 5 most recent snapshots SHALL be retained

#### Scenario: Snapshots sorted by timestamp
**Given** multiple snapshots exist  
**When** the system lists snapshots  
**Then** snapshots SHALL be ordered by timestamp descending (newest first)  
**And** the most recent snapshot SHALL be first in the list

---

### Requirement: Snapshot Loading on Startup
The system SHALL load the most recent snapshot into memory when the backend starts.

#### Scenario: Latest snapshot loaded on startup
**Given** snapshot files exist in the snapshots directory  
**When** the backend container starts  
**Then** the system SHALL identify the most recent snapshot  
**And** the system SHALL load the snapshot data into the in-memory database  
**And** all tables and data SHALL be restored

#### Scenario: Startup with no existing snapshots
**Given** no snapshot files exist  
**When** the backend container starts  
**Then** the system SHALL initialize an empty in-memory database  
**And** the system SHALL NOT fail or error  
**And** the application SHALL be ready to accept new data

---

### Requirement: Change Detection
The system SHALL detect when database content has changed to determine if a snapshot is needed.

#### Scenario: Change detected after data insertion
**Given** a snapshot was created at time T  
**And** new data is inserted into the projects table  
**When** the change detection runs  
**Then** the system SHALL detect that data has changed  
**And** the system SHALL mark the database as requiring a snapshot

#### Scenario: No change detected when data is unchanged
**Given** a snapshot was created at time T  
**And** no data modifications have occurred  
**When** the change detection runs  
**Then** the system SHALL detect that data has NOT changed  
**And** the system SHALL NOT create a new snapshot

---

### Requirement: Snapshot File Format
Snapshots SHALL use DuckDB's native `EXPORT DATABASE` format for ACID compliance and schema fidelity.

#### Scenario: Snapshot preserves all schema and data
**Given** the in-memory database contains tables, indexes, and data  
**When** a snapshot is created using EXPORT DATABASE  
**Then** the snapshot file SHALL contain all table schemas  
**And** the snapshot file SHALL contain all data rows  
**And** the snapshot file SHALL contain all indexes and constraints  
**And** the snapshot SHALL be loadable via IMPORT DATABASE

---

### Requirement: Snapshot API Endpoint
The system SHALL provide an API endpoint to list available snapshots with metadata.

#### Scenario: List all snapshots
**Given** 3 snapshots exist in the snapshots directory  
**When** a GET request is made to `/api/v1/snapshots`  
**Then** the response SHALL return a list of 3 snapshots  
**And** each snapshot SHALL include: `id`, `timestamp`, `file_size_bytes`, `record_count`  
**And** snapshots SHALL be ordered by timestamp descending

#### Scenario: Get snapshot details
**Given** a snapshot with ID `20260109_212015` exists  
**When** a GET request is made to `/api/v1/snapshots/20260109_212015`  
**Then** the response SHALL return the snapshot metadata  
**And** the response SHALL include: `id`, `timestamp`, `file_size_bytes`, `record_count`, `file_path`

---

