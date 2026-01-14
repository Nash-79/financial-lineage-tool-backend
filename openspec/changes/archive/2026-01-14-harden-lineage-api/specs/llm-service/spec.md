## ADDED Requirements
### Requirement: Embed Calls Must Include Model Parameter
The system SHALL require an explicit model parameter for all embedding calls.

#### Scenario: Legacy ingestion embeds supply model
- **WHEN** legacy ingestion calls `embed()` for code chunks
- **THEN** the call includes the embedding model from configuration
- **AND** missing/invalid model triggers a clear error before the Ollama request
- **AND** ingestion continues to process remaining chunks even if one embed fails
