## ADDED Requirements

### Requirement: Custom RAG Observability Metrics
The system SHALL emit custom OpenTelemetry metrics for RAG pipeline operations and performance monitoring.

#### Scenario: RAG query latency metrics
- **WHEN** RAG query is executed
- **THEN** system emits histogram metric "rag.query.latency_ms" with labels (endpoint, cache_hit)
- **AND** it tracks p50, p95, p99 latencies
- **AND** metrics are exported to OTLP endpoint
- **AND** metrics can be visualized in SigNoz/Grafana

#### Scenario: Cache performance metrics
- **WHEN** embedding or query cache is accessed
- **THEN** system emits counter metrics "rag.cache.hits" and "rag.cache.misses"
- **AND** it emits gauge metric "rag.cache.hit_rate" updated every 60 seconds
- **AND** metrics include labels (cache_type: embedding|query)
- **AND** alerting can be configured on hit_rate < 0.4

#### Scenario: Ollama OOM error tracking
- **WHEN** Ollama returns OOM error
- **THEN** system emits counter metric "ollama.oom_errors" with labels (model, context_size)
- **AND** it increments counter immediately on error
- **AND** alert is triggered for any OOM error count > 0
- **AND** metric helps diagnose memory issues

#### Scenario: Inference routing metrics
- **WHEN** inference request is routed
- **THEN** system emits counter metric "inference.requests" with labels (provider: ollama|groq|openrouter, success: true|false)
- **AND** it tracks fallback rate (groq_requests / total_requests)
- **AND** it emits cost estimate gauge "inference.estimated_cost_usd"
- **AND** metrics show cost savings from local-first strategy

#### Scenario: SLO compliance metrics
- **WHEN** system processes requests
- **THEN** it tracks SLO compliance for each endpoint
- **AND** it emits gauge "slo.latency_p95_ms" with target threshold
- **AND** it emits gauge "slo.availability_pct" updated every 5 minutes
- **AND** dashboards show red/yellow/green SLO status
