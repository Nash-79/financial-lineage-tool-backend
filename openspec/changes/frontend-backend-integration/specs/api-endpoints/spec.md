# api-endpoints Specification

## MODIFIED Requirements

### Requirement: Chat Endpoints
The system SHALL provide multiple chat endpoints for different query types with proper error handling

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

### Requirement: Activity and Monitoring Endpoints
The system SHALL provide endpoints for activity tracking with reliable persistence

#### Scenario: Activity event persistence
- **WHEN** system activity occurs (ingestion, query, error)
- **THEN** activity event is persisted to storage
- **AND** persistence callback is async callable function
- **AND** persistence failures are logged but don't block operations
- **AND** failed events are retried or queued

#### Scenario: Activity tracker initialization
- **WHEN** middleware initializes activity tracker
- **THEN** tracker receives valid callable for persistence
- **AND** callable accepts event data as parameter
- **AND** callable returns success/failure status
- **AND** initialization errors fail startup with clear message

## ADDED Requirements

### Requirement: Pydantic Model Validation
API models SHALL be fully defined without forward reference errors

#### Scenario: OpenAPI schema generation
- **WHEN** FastAPI generates OpenAPI schema at startup
- **THEN** all Pydantic models are fully resolved
- **AND** no forward reference errors occur
- **AND** schema generation completes without warnings
- **AND** /docs endpoint renders successfully

#### Scenario: Type annotation imports
- **WHEN** API model uses Dict, List, Any types
- **THEN** types are imported explicitly from typing module
- **AND** no forward references to undefined types
- **AND** Annotated types are properly configured
- **AND** all referenced models are defined before use

#### Scenario: Model rebuilding
- **WHEN** Pydantic model uses forward references
- **THEN** model calls .model_rebuild() after all types defined
- **AND** rebuild completes without errors
- **AND** rebuilt model validates correctly
- **AND** OpenAPI schema includes rebuilt model

### Requirement: Admin Restart Endpoint
System SHALL provide endpoint to trigger graceful container restart

#### Scenario: Admin restart request
- **WHEN** frontend sends POST to /admin/restart
- **THEN** endpoint returns 200 with {"status": "restarting"}
- **AND** endpoint triggers Docker container restart
- **AND** Docker restart policy brings container back up
- **AND** response is sent before restart begins

#### Scenario: Restart endpoint availability
- **WHEN** frontend checks if restart endpoint exists
- **THEN** OPTIONS /admin/restart returns 200 or 204
- **AND** endpoint appears in OpenAPI docs
- **AND** endpoint is registered in FastAPI routes
- **AND** endpoint path matches frontend expectations

#### Scenario: Restart graceful shutdown
- **WHEN** restart is triggered
- **THEN** system closes active connections gracefully
- **AND** system waits for in-flight requests to complete
- **AND** system persists any pending activity events
- **AND** system exits with code 0 for Docker restart

### Requirement: API Error Responses
All endpoints SHALL return consistent error response format

#### Scenario: Standard error response
- **WHEN** endpoint encounters error
- **THEN** response contains "detail" field with error message
- **AND** response includes appropriate HTTP status code
- **AND** 500 errors include component that failed
- **AND** 400 errors include validation details

#### Scenario: Error logging
- **WHEN** endpoint returns error response
- **THEN** error is logged with request context
- **AND** log includes endpoint path and method
- **AND** log includes error type and message
- **AND** 500 errors include stack trace in logs

#### Scenario: Service unavailable errors
- **WHEN** backend service is unavailable (Ollama, Neo4j, Qdrant)
- **THEN** endpoint returns 503 Service Unavailable
- **AND** error message indicates which service is down
- **AND** error message includes troubleshooting hints
- **AND** health check endpoint reflects service status
