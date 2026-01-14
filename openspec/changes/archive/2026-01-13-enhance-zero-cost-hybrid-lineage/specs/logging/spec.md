# logging Spec Deltas

## ADDED Requirements

### Requirement: Ingestion Agent Logging
The system SHALL record validation and KG agent outputs in ingestion logs.

#### Scenario: Validation log entry
- **WHEN** validation agent completes post-ingestion
- **THEN** ingestion logs include validation status and gap summary
- **AND** entry includes file_path and ingestion_id

#### Scenario: KG agent log entry
- **WHEN** KG enrichment agent writes edges to Neo4j
- **THEN** ingestion logs include edge counts and model name
- **AND** entry includes confidence statistics (min/avg/max)

### Requirement: Graph Snapshot Logging
The system SHALL log pre-ingestion Neo4j snapshot artifacts.

#### Scenario: Snapshot artifact reference
- **WHEN** snapshot is created before ingestion
- **THEN** ingestion logs include the snapshot artifact path
- **AND** log entry includes node and edge counts
- **AND** log entry includes project name and ingestion_id
