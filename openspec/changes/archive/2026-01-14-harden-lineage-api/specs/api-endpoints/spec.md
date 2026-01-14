## ADDED Requirements
### Requirement: Secure Admin Restart Endpoint
The system SHALL protect the admin restart endpoint to prevent unauthorized process restarts.

#### Scenario: Auth required for restart
- **WHEN** a client calls `/admin/restart`
- **THEN** the request MUST be authenticated/authorized (or restricted to local/dev mode)
- **AND** unauthorized requests receive 401/403
- **AND** successful calls return a confirmation before shutdown/restart begins

#### Scenario: Restart disabled in prod by default
- **WHEN** the service runs in production configuration
- **THEN** `/admin/restart` is disabled or requires explicit feature flag to enable
- **AND** requests without the flag return 404/403

### Requirement: Validate Lineage Node Type Filter
The system SHALL validate lineage node type filters to prevent Cypher injection and malformed queries.

#### Scenario: Whitelisted type labels only
- **WHEN** a client requests `/api/v1/lineage/nodes?type=Table`
- **THEN** the type value is validated against a known whitelist (e.g., Table, Column, View)
- **AND** invalid values return 422 with a clear message
- **AND** Cypher queries are built with parameterization or safe label insertion

### Requirement: Graph-Aware Chat Responses
The system SHALL generate graph-aware chat responses using accurate graph statistics.

#### Scenario: Stats use node type counts
- **WHEN** generating graph-aware prompts
- **THEN** the system uses node type counts from `node_types` (e.g., Table, View, Column)
- **AND** reported counts match `get_stats()` results
- **AND** missing types default to zero without breaking the prompt
