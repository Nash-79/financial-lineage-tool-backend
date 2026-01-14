# database-query-interface Specification

## Purpose
TBD - created by archiving change inmemory-duckdb-snapshots. Update Purpose after archive.
## Requirements
### Requirement: Execute DuckDB Queries via API
The system SHALL provide an API endpoint to execute custom DuckDB SQL queries against either the live in-memory database or a specific snapshot.

#### Scenario: Execute query on live database
**Given** the in-memory database contains project data  
**When** a POST request is made to `/api/v1/database/query` with `{sql: "SELECT * FROM projects"}`  
**Then** the system SHALL execute the query on the live in-memory database  
**And** the response SHALL return query results with columns and rows  
**And** the response format SHALL be: `{columns: string[], rows: any[][], row_count: number}`

#### Scenario: Execute query on snapshot
**Given** a snapshot with ID `20260109_212015` exists  
**When** a POST request is made to `/api/v1/database/query` with `{sql: "SELECT * FROM projects", snapshot_id: "20260109_212015"}`  
**Then** the system SHALL load the snapshot in read-only mode  
**And** the system SHALL execute the query on the snapshot database  
**And** the system SHALL return the query results  
**And** the system SHALL close the snapshot connection after query execution

#### Scenario: Query validation prevents SQL injection
**Given** a malicious SQL query is submitted  
**When** the query contains DROP, DELETE, or UPDATE statements  
**Then** the system SHALL reject the query  
**And** the response SHALL return an error message  
**And** the database SHALL NOT be modified

#### Scenario: Query timeout prevents long-running queries
**Given** a complex query is submitted  
**When** the query execution exceeds 30 seconds  
**Then** the system SHALL terminate the query  
**And** the response SHALL return a timeout error  
**And** system resources SHALL be released

---

### Requirement: Frontend Snapshot Selector
The frontend Database page SHALL provide a UI component to select between the live database and available snapshots.

#### Scenario: Display snapshot list in selector
**Given** the Database page is loaded  
**And** 3 snapshots exist  
**When** the snapshot selector component renders  
**Then** the selector SHALL display "Live Database (In-Memory)" as the first option  
**And** the selector SHALL display 3 snapshot options  
**And** snapshot options SHALL show timestamps in descending order  
**And** each snapshot SHALL display: timestamp, file size

#### Scenario: Select live database
**Given** the snapshot selector is displayed  
**When** the user selects "Live Database (In-Memory)"  
**Then** the selected database SHALL be set to live  
**And** subsequent queries SHALL execute against the in-memory database

#### Scenario: Select snapshot
**Given** the snapshot selector is displayed  
**When** the user selects snapshot "2026-01-09 21:20:15"  
**Then** the selected database SHALL be set to that snapshot ID  
**And** subsequent queries SHALL execute against that snapshot

---

### Requirement: Frontend Query Interface
The frontend Database page SHALL provide a UI component to input and execute DuckDB SQL queries.

#### Scenario: Input and execute SQL query
**Given** the query interface is displayed  
**And** "Live Database" is selected  
**When** the user enters `SELECT * FROM projects` in the SQL input  
**And** the user clicks "Execute Query"  
**Then** the system SHALL send the query to the backend API  
**And** the system SHALL display a loading indicator  
**And** the system SHALL display the query results in a table format

#### Scenario: Display query results
**Given** a query has been executed successfully  
**When** the results are returned from the API  
**Then** the interface SHALL display column headers  
**And** the interface SHALL display all result rows  
**And** the interface SHALL display the total row count  
**And** the table SHALL be scrollable if results exceed viewport height

#### Scenario: Display query error
**Given** an invalid SQL query is submitted  
**When** the API returns an error response  
**Then** the interface SHALL display the error message  
**And** the error message SHALL be clearly visible  
**And** the previous results SHALL be cleared

#### Scenario: Query examples provided
**Given** the query interface is displayed  
**When** the user views the interface  
**Then** helpful query examples SHALL be displayed  
**And** examples SHALL include: `SELECT * FROM projects`, `SELECT COUNT(*) FROM files`, `SELECT * FROM runs ORDER BY created_at DESC LIMIT 10`  
**And** clicking an example SHALL populate the SQL input

---

### Requirement: Read-Only Query Execution
All queries executed via the query interface SHALL be read-only to prevent accidental data modification.

#### Scenario: SELECT queries allowed
**Given** the query interface is displayed  
**When** the user submits a SELECT query  
**Then** the query SHALL execute successfully  
**And** results SHALL be returned

#### Scenario: INSERT queries rejected
**Given** the query interface is displayed  
**When** the user submits an INSERT query  
**Then** the query SHALL be rejected  
**And** an error message SHALL be displayed  
**And** the database SHALL NOT be modified

#### Scenario: UPDATE queries rejected
**Given** the query interface is displayed  
**When** the user submits an UPDATE query  
**Then** the query SHALL be rejected  
**And** an error message SHALL be displayed  
**And** the database SHALL NOT be modified

#### Scenario: DELETE queries rejected
**Given** the query interface is displayed  
**When** the user submits a DELETE query  
**Then** the query SHALL be rejected  
**And** an error message SHALL be displayed  
**And** the database SHALL NOT be modified

#### Scenario: DDL queries rejected
**Given** the query interface is displayed  
**When** the user submits a CREATE, ALTER, or DROP query  
**Then** the query SHALL be rejected  
**And** an error message SHALL be displayed  
**And** the database schema SHALL NOT be modified

---

### Requirement: Query Performance
Query execution SHALL be fast and responsive for typical metadata queries.

#### Scenario: Live database query performance
**Given** the in-memory database contains 1000 projects  
**When** a SELECT query is executed on the live database  
**Then** the query SHALL complete in less than 100ms  
**And** results SHALL be returned to the frontend

#### Scenario: Snapshot query performance
**Given** a snapshot contains 1000 projects  
**When** a SELECT query is executed on the snapshot  
**Then** the query SHALL complete in less than 500ms (including snapshot load time)  
**And** results SHALL be returned to the frontend

---

