## ADDED Requirements
### Requirement: Preserve relative source paths for ingested files
The system SHALL persist the original relative path for files ingested via upload and GitHub.

#### Scenario: Folder upload path retention
- **WHEN** a user uploads a folder with nested files
- **THEN** the system stores files under `run_dir/raw_source/<relative_path>`
- **AND** the metadata store records `relative_path` for each file
- **AND** file listings can reconstruct the folder tree from stored paths

#### Scenario: GitHub path retention
- **WHEN** GitHub ingestion processes repository files
- **THEN** the system stores files with their repository-relative path
- **AND** the metadata store records the original path and source repository
