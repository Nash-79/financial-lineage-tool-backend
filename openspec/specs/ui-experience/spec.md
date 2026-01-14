# ui-experience Specification

## Purpose
TBD - created by archiving change align-frontend-backend-api. Update Purpose after archive.
## Requirements
### Requirement: File upload UI honors backend-configured policies
The system SHALL reflect backend file-upload policies in the upload UI.

#### Scenario: Enforce allowed extensions and size
- **WHEN** user selects files to upload
- **THEN** the UI enforces allowed extensions and max size from `/api/v1/files/config`
- **AND** validation messages are shown before network calls

#### Scenario: Capture ingestion instructions
- **WHEN** user uploads files
- **THEN** the UI allows entering optional text/markdown instructions to guide lineage extraction
- **AND** the instructions are sent with the upload request or stored alongside the run

### Requirement: Chat UI supports low-latency local mode
The system SHALL provide chat options that improve perceived latency for local Ollama use.

#### Scenario: Streaming deep chat
- **WHEN** user enables streaming
- **THEN** the UI uses `/api/chat/deep/stream` and renders tokens incrementally
- **AND** falls back to non-streaming if streaming fails

#### Scenario: Skip memory for speed
- **WHEN** user toggles skip-memory
- **THEN** requests include `skip_memory=true`
- **AND** the UI communicates reduced context but faster responses

#### Scenario: Context length guidance
- **WHEN** user is in local/Ollama mode
- **THEN** the UI displays guidance on model context limits and potential truncation with long prompts
- **AND** suggests smaller prompts or streaming for responsiveness

