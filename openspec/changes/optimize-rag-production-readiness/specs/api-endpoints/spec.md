## ADDED Requirements

### Requirement: JWT Authentication
The system SHALL authenticate all API requests using JWT tokens, except health check endpoints.

#### Scenario: JWT token validation
- **WHEN** request is made to protected endpoint
- **THEN** system extracts Bearer token from Authorization header
- **AND** it validates JWT signature using JWT_SECRET_KEY
- **AND** it checks token expiration timestamp
- **AND** if valid, request proceeds with user_id from token payload
- **AND** if invalid or expired, return 401 Unauthorized

#### Scenario: Token generation on login
- **WHEN** user successfully authenticates via /api/auth/login
- **THEN** system generates JWT token with payload (user_id, role, exp)
- **AND** token expiration is set to 24 hours from issue time
- **AND** token is signed with HS256 algorithm
- **AND** response includes token and user metadata

#### Scenario: Public health endpoints
- **WHEN** request is made to /health or /health/*
- **THEN** no authentication is required
- **AND** endpoint returns status without token check
- **AND** sensitive details (credentials, internal IPs) are excluded

#### Scenario: API key authentication for services
- **WHEN** service-to-service call is made with X-API-Key header
- **THEN** system validates key against stored API keys in database
- **AND** it associates request with service account
- **AND** it logs service API key usage
- **AND** API keys can be rotated without affecting JWT users

### Requirement: Rate Limiting
The system SHALL enforce rate limits on API endpoints to prevent abuse and ensure fair usage.

#### Scenario: Per-user rate limits
- **WHEN** authenticated user makes requests
- **THEN** system tracks request count per user per time window
- **AND** default limit is 100 requests per 10 minutes
- **AND** if limit exceeded, return 429 Too Many Requests
- **AND** response includes Retry-After header

#### Scenario: Per-endpoint rate limits
- **WHEN** request is made to /api/chat/deep
- **THEN** system enforces stricter limit (10 requests per minute)
- **AND** /api/chat/semantic has limit of 30 requests per minute
- **AND** /api/files/upload has limit of 5 requests per minute
- **AND** limits are configurable via environment variables

#### Scenario: Anonymous rate limits
- **WHEN** request is made without authentication (if allowed)
- **THEN** system applies IP-based rate limiting
- **AND** limit is 20 requests per minute per IP
- **AND** rate limit counters are stored in Redis
- **AND** counters expire automatically after time window

#### Scenario: Rate limit headers
- **WHEN** rate-limited request is processed
- **THEN** response includes X-RateLimit-Limit header (total allowed)
- **AND** it includes X-RateLimit-Remaining header (requests left)
- **AND** it includes X-RateLimit-Reset header (timestamp of window reset)
- **AND** headers allow clients to implement backoff

### Requirement: Audit Logging
The system SHALL log all sensitive operations to immutable audit log for compliance and security monitoring.

#### Scenario: Ingestion audit log
- **WHEN** files are ingested via /api/v1/files/upload
- **THEN** system logs event with (timestamp, user_id, file_count, file_names, project_id)
- **AND** log entry is written to audit log storage (append-only)
- **AND** log includes client IP address and user agent
- **AND** log cannot be modified or deleted by application

#### Scenario: Query audit log
- **WHEN** RAG query is executed via /api/chat/*
- **THEN** system logs event with (timestamp, user_id, query_text_hash, query_type, latency_ms)
- **AND** full query text is logged only if AUDIT_LOG_FULL_QUERIES=true
- **AND** log includes response status (success, error, timeout)
- **AND** sensitive PII in queries is redacted per regex rules

#### Scenario: Admin action audit log
- **WHEN** admin performs privileged action (delete project, modify user role)
- **THEN** system logs event with (timestamp, admin_user_id, action_type, target_resource, metadata)
- **AND** log includes before/after state for modifications
- **AND** log entry is written synchronously (cannot be lost)
- **AND** failed admin actions are also logged

#### Scenario: Audit log retention
- **WHEN** audit logs are older than AUDIT_LOG_RETENTION_DAYS (default: 90)
- **THEN** system archives logs to cold storage (S3, Glacier)
- **AND** archived logs are compressed and encrypted
- **AND** active audit log table is partitioned by month
- **AND** retention policy complies with regulatory requirements

### Requirement: Secure Configuration Management
The system SHALL require all sensitive credentials via environment variables and reject hardcoded defaults in production.

#### Scenario: Required credentials validation
- **WHEN** system starts in production mode (ENVIRONMENT=production)
- **THEN** it validates NEO4J_PASSWORD is set via environment variable
- **AND** it validates JWT_SECRET_KEY is set and >= 32 characters
- **AND** it validates ALLOWED_ORIGINS is explicitly configured
- **AND** if any required variable is missing, system fails to start with clear error

#### Scenario: Development mode defaults
- **WHEN** system starts in development mode (ENVIRONMENT=development)
- **THEN** it allows default values for non-sensitive config (OLLAMA_HOST=localhost)
- **AND** it logs warnings for missing credentials
- **AND** it does not fail startup but marks services as degraded

#### Scenario: CORS origin validation
- **WHEN** cross-origin request is received in production
- **THEN** system checks Origin header against ALLOWED_ORIGINS list
- **AND** only exact matches are allowed (no wildcards in production)
- **AND** rejected origins return 403 Forbidden
- **AND** ALLOWED_ORIGINS cannot be "*" in production mode

#### Scenario: Credential exposure prevention
- **WHEN** /health or /api/config endpoints return system info
- **THEN** passwords, API keys, and secrets are redacted
- **AND** only non-sensitive config is returned (timeouts, feature flags)
- **AND** environment variables are never echoed in responses
- **AND** logs mask credentials with "***" before writing
