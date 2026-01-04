## ADDED Requirements

### Requirement: Streaming Chat Endpoint
The system SHALL provide a streaming endpoint for real-time chat responses via Server-Sent Events.

#### Scenario: Stream deep analysis response
- **WHEN** client sends POST to /api/chat/deep/stream
- **THEN** server returns Content-Type: text/event-stream
- **AND** response tokens are sent as SSE data events
- **AND** each event contains partial response text
- **AND** final event contains sources and metadata

#### Scenario: Stream error handling
- **WHEN** error occurs during streaming
- **THEN** server sends SSE error event with details
- **AND** connection is closed gracefully
- **AND** client receives actionable error message

#### Scenario: Stream cancellation
- **WHEN** client closes connection during streaming
- **THEN** server stops LLM generation
- **AND** resources are cleaned up
- **AND** no error is logged for client-initiated close

### Requirement: Chat Session Title Generation
The system SHALL provide an endpoint to generate session titles from chat messages.

#### Scenario: Generate title from first message
- **WHEN** client sends POST to /api/chat/title with query
- **THEN** server returns descriptive title (15-30 characters)
- **AND** title summarizes the query topic
- **AND** response time is under 2 seconds

#### Scenario: Title generation fallback
- **WHEN** LLM title generation fails
- **THEN** server returns truncated query as fallback title
- **AND** no error is returned to client
- **AND** fallback is limited to 50 characters

### Requirement: Chat Session Memory Management
The system SHALL provide endpoints to manage chat session memory.

#### Scenario: Delete session memory
- **WHEN** client sends DELETE to /api/chat/session/{session_id}
- **THEN** server schedules memory deletion in background
- **AND** returns 202 Accepted with status message
- **AND** all vectors for session are removed from Qdrant

## MODIFIED Requirements

### Requirement: Chat Endpoints
The system SHALL provide multiple chat endpoints for different query types with proper error handling and optional memory context.

#### Scenario: Chat endpoint error handling
- **WHEN** chat endpoint encounters LLM error
- **THEN** endpoint returns 500 with descriptive error message
- **AND** error details include which component failed
- **AND** error is logged with full stack trace
- **AND** user receives actionable error message

#### Scenario: Chat endpoint model configuration
- **WHEN** chat endpoint calls Ollama generate
- **THEN** call includes model parameter from config.LLM_MODEL
- **AND** model parameter is required and validated
- **AND** missing model parameter causes clear error
- **AND** unsupported model name returns helpful error

#### Scenario: Chat request with session memory
- **WHEN** client sends chat request with session_id
- **THEN** system retrieves relevant memory context from vector store
- **AND** memory context is prepended to query context
- **AND** memory retrieval runs in parallel with other operations

#### Scenario: Chat request without memory
- **WHEN** client sends chat request with skip_memory=true
- **THEN** system bypasses memory context retrieval
- **AND** saves ~300ms latency
- **AND** query proceeds with empty memory context

#### Scenario: Chat response with graph visualization
- **WHEN** deep analysis finds graph entities
- **THEN** response includes graph_data field
- **AND** graph_data contains nodes and edges arrays
- **AND** nodes include id, label, and type
- **AND** edges include source, target, and relationship type
