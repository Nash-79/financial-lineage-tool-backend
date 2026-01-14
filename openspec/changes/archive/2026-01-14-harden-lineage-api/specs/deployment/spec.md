## ADDED Requirements
### Requirement: No Hardcoded Secrets in Defaults
The system SHALL forbid hardcoded secrets (e.g., database passwords) in configuration defaults and fail closed when required credentials are missing.

#### Scenario: Neo4j password must come from environment
- **WHEN** the service initializes Neo4j configuration
- **THEN** it requires `NEO4J_PASSWORD` (and other required creds) from environment or secret store
- **AND** no default password is baked into the codebase
- **AND** startup fails with a clear error if credentials are absent
