## ADDED Requirements

### Requirement: Dashboard displays comprehensive system health

The dashboard SHALL display detailed health status for all system components with actionable information.

#### Scenario: System health card shows all services

- **WHEN** user views the dashboard
- **THEN** system health card displays status for Ollama, Qdrant, Neo4j, Redis, OpenRouter
- **AND** each service shows "healthy", "degraded", or "unhealthy" with color indicator
- **AND** services can be expanded to show detailed metrics
- **AND** last-checked timestamp is displayed

#### Scenario: DuckDB status visibility

- **WHEN** user views the dashboard
- **THEN** database status section shows DuckDB mode (memory/file)
- **AND** shows connection pool stats if available (active, available, max)
- **AND** shows last snapshot timestamp and path
- **AND** shows pending changes indicator if data changed since last snapshot

#### Scenario: Expandable service details

- **WHEN** user clicks on a service row in health card
- **THEN** row expands to show detailed metrics
- **AND** for Ollama: shows loaded models, memory usage
- **AND** for Qdrant: shows collection count, vector count
- **AND** for Neo4j: shows node count, relationship count
- **AND** collapsed by default to reduce visual noise

### Requirement: Dashboard displays model availability by chat mode

The dashboard SHALL show chat mode readiness with clear visual indicators.

#### Scenario: Chat mode status display

- **WHEN** user views the dashboard
- **THEN** model availability widget shows all chat modes (deep, semantic, graph, text)
- **AND** each mode displays green checkmark if fully configured and provider available
- **AND** each mode displays yellow warning if configured but provider degraded
- **AND** each mode displays red X if not configured or provider unavailable

#### Scenario: Provider status in model availability

- **WHEN** user views model availability widget
- **THEN** widget shows Ollama and OpenRouter provider status
- **AND** shows "Connected" or "Offline" for each provider
- **AND** shows API key configured status for OpenRouter (not the key itself)
- **AND** shows count of models available from each provider

#### Scenario: Navigate to model configuration

- **WHEN** user clicks on a chat mode in availability widget
- **THEN** user is navigated to model configuration page
- **AND** relevant usage type is pre-selected or highlighted
- **AND** user can quickly add missing configuration

### Requirement: Dashboard displays log summary with error indicators

The dashboard SHALL show log health summary with prominent error visibility.

#### Scenario: Log summary widget display

- **WHEN** user views the dashboard
- **THEN** log summary widget shows per-category log counts (app, chat, audit, ingestion)
- **AND** categories with errors show red badge with error count
- **AND** categories without errors show green indicator
- **AND** total error count for last 24 hours is prominently displayed

#### Scenario: Latest error preview

- **WHEN** errors exist in the last 24 hours
- **THEN** log summary shows latest error message (truncated)
- **AND** shows error timestamp and category
- **AND** clicking error navigates to log viewer with that entry selected

#### Scenario: Navigate to log viewer from summary

- **WHEN** user clicks on a category in log summary widget
- **THEN** user is navigated to log viewer page
- **AND** category filter is pre-applied
- **AND** time range is set to last 24 hours

### Requirement: Dashboard displays configuration completeness

The dashboard SHALL indicate system configuration status with actionable guidance.

#### Scenario: Configuration status card display

- **WHEN** user views the dashboard
- **THEN** configuration status card shows checklist of required configurations
- **AND** checklist includes: model configs, API keys, database connection, feature flags
- **AND** completed items show checkmark, missing items show warning icon
- **AND** overall completeness percentage is displayed

#### Scenario: Missing configuration guidance

- **WHEN** a required configuration is missing
- **THEN** configuration status card shows specific guidance
- **AND** guidance includes what's missing and how to resolve
- **AND** quick action link navigates to relevant settings page

#### Scenario: Feature flags visibility

- **WHEN** user views configuration status card
- **THEN** active feature flags are displayed (USE_LLAMAINDEX, ENABLE_HYBRID_SEARCH)
- **AND** each flag shows enabled/disabled status
- **AND** tooltip explains what each flag controls

### Requirement: Dashboard supports widget-level refresh

Each dashboard widget SHALL support independent refresh with loading states.

#### Scenario: Individual widget refresh

- **WHEN** user clicks refresh button on a specific widget
- **THEN** only that widget shows loading state
- **AND** other widgets remain interactive
- **AND** widget updates with fresh data on completion
- **AND** last-updated timestamp updates

#### Scenario: Global dashboard refresh

- **WHEN** user clicks global refresh button
- **THEN** all widgets refresh in parallel
- **AND** each widget shows individual loading state
- **AND** widgets complete independently
- **AND** failed widgets show error state without blocking others

#### Scenario: Widget error isolation

- **WHEN** a widget's API call fails
- **THEN** that widget shows error state with retry button
- **AND** other widgets continue to function normally
- **AND** error message indicates what failed
- **AND** user can retry individual widget

### Requirement: Dashboard layout is responsive and collapsible

The dashboard layout SHALL adapt to screen size and user preferences.

#### Scenario: Responsive grid layout

- **WHEN** user views dashboard on large screen (>1200px)
- **THEN** widgets display in multi-column grid layout
- **AND** primary stats in top row, detail widgets below

#### Scenario: Collapsed sections for power users

- **WHEN** user clicks collapse button on a widget section
- **THEN** section collapses to show only header
- **AND** collapse state persists in local storage
- **AND** collapsed sections can be expanded with one click

#### Scenario: Mobile-friendly layout

- **WHEN** user views dashboard on small screen (<768px)
- **THEN** widgets stack vertically in single column
- **AND** critical information remains visible without scrolling
- **AND** touch targets are appropriately sized

## MODIFIED Requirements

### Requirement: Chat UI supports low-latency local mode

The system SHALL provide chat options that improve perceived latency for local Ollama use, with visibility into model availability.

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

#### Scenario: Model availability indicator in chat

- **WHEN** user is on chat page
- **THEN** current chat mode shows availability status from dashboard data
- **AND** unavailable modes show warning with link to configuration
- **AND** user can see which provider will handle their request
