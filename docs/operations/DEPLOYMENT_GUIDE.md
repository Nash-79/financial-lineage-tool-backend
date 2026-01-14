# Deployment Guide - Optimized Data Ingestion Pipeline

**Document Version**: 1.0.0
**Last Updated**: December 30, 2025
**Target**: Production Deployment

---

## Overview

This guide provides step-by-step instructions for deploying the optimized data ingestion pipeline to production. The deployment uses **feature flags** for safe, gradual rollout and quick rollback capability.

**Performance Target**: 10-15x throughput improvement
**Deployment Time**: 1-2 hours (gradual rollout)
**Rollback Time**: < 5 minutes

---

## Production Environment Variables

### 🔒 Required for Production Deployment

The following environment variables **MUST** be set before deploying to production. The application will fail to start if these are missing or invalid when `ENVIRONMENT=production`.

**Security-Critical Variables**:

```bash
# Environment mode (REQUIRED)
ENVIRONMENT=production  # Enables strict validation

# Neo4j Database Credentials (REQUIRED)
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-secure-password-here  # Min 8 characters, NO HARDCODED VALUES
NEO4J_DATABASE=neo4j

# JWT Authentication (REQUIRED)
JWT_SECRET_KEY=your-secret-key-min-32-chars  # Generate with: openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS Configuration (REQUIRED)
ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com  # NO wildcards in production
```

**How to generate secure credentials**:

```bash
# Generate JWT secret key (32+ characters)
openssl rand -hex 32

# Verify NEO4J_PASSWORD is set
echo $NEO4J_PASSWORD  # Should output your password, not empty
```

**Validation**:
The application automatically validates production configuration on startup. If validation fails, you'll see error messages like:

```
Production configuration validation failed:
  - NEO4J_PASSWORD must be set via environment variable in production
  - JWT_SECRET_KEY must be at least 32 characters for security
  - ALLOWED_ORIGINS must be explicitly configured (wildcards not allowed in production)
```

### ⚙️ Optional Production Variables

**Inference Fallback** (cloud providers for OOM prevention):

```bash
# Inference fallback provider (optional, default: openrouter)
INFERENCE_FALLBACK_PROVIDER=openrouter  # Options: openrouter, none

# OpenRouter API (free tier available)
OPENROUTER_API_KEY=your-openrouter-key  # Get from https://openrouter.ai/

# Default cloud model (OpenRouter free-tier)
INFERENCE_DEFAULT_MODEL=google/gemini-2.0-flash-exp:free
```

**Observability** (SigNoz/OpenTelemetry):

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=financial-lineage-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://signoz-host:4318
```

**Hybrid Search (Qdrant sparse + dense)**:

```bash
# Enable hybrid search for new collections
ENABLE_HYBRID_SEARCH=true
```

**Upgrade note**: Existing Qdrant collections created without sparse vectors will continue
to run dense-only searches. To enable hybrid search, create a new collection and re-index
the corpus (or follow your migration script to copy vectors into a new collection).

**Parser Plugin Configuration**:

```bash
# Enable parser plugins (comma-separated class paths)
LINEAGE_PLUGINS=src.ingestion.plugins.sql_standard.StandardSqlPlugin,src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin,src.ingestion.plugins.json_enricher.JsonEnricherPlugin

# Optional plugin configuration (JSON string)
LINEAGE_PLUGIN_CONFIG_JSON={"src.ingestion.plugins.sql_standard.StandardSqlPlugin":{"default_dialect":"duckdb"},"src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin":{"prefer_ast_for_small_files":true,"ast_max_lines":100,"sql_extraction_enabled":true}}
```

**Tree-sitter Python Dependencies**:

```bash
# Ensure tree-sitter dependencies are installed
pip install tree-sitter tree-sitter-python
```

**Rate Limiting** (optional, prevents abuse):

```bash
RATE_LIMIT_PER_USER=100  # Requests per 10 minutes
RATE_LIMIT_CHAT_DEEP=10  # Deep chat requests per minute
RATE_LIMIT_CHAT_SEMANTIC=30  # Semantic chat requests per minute
RATE_LIMIT_FILES_UPLOAD=5  # File uploads per minute
```

**GitHub OAuth** (optional, for GitHub integration):

```bash
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=https://app.example.com/connectors/github/callback
```

**Audit Logging** (optional, for compliance):

```bash
AUDIT_LOG_FULL_QUERIES=false  # Set to true to log full query text (default: hash only)
AUDIT_LOG_RETENTION_DAYS=90  # Audit log retention period
```

### 📋 Complete .env Template

Copy [../../.env.example](../../.env.example) to `.env` and fill in your production values:

```bash
cp .env.example .env
vi .env  # Edit with production credentials
```

**DO NOT commit .env to version control!** Add to `.gitignore`:
```bash
echo ".env" >> .gitignore
```

---

## Pre-Deployment Checklist

### ✅ Required Before Deployment

- [ ] All code changes merged to main branch
- [ ] Tests passing (99% coverage - 66/67 tests)
- [ ] **Production environment variables configured** (see above)
- [ ] **JWT_SECRET_KEY generated** (min 32 characters)
- [ ] **NEO4J_PASSWORD set** (no hardcoded credentials)
- [ ] **ALLOWED_ORIGINS configured** (no wildcards)
- [ ] Staging environment tested successfully
- [ ] SigNoz observability configured (OTLP enabled)
- [ ] Backup of current production data
- [ ] Rollback procedures reviewed by team
- [ ] Deployment window scheduled (low-traffic period recommended)
- [ ] On-call engineer identified
- [ ] Stakeholders notified of deployment

### ✅ Infrastructure Requirements

- [ ] Python 3.10+ installed
- [ ] Neo4j 4.0+ accessible
- [ ] OTLP endpoint (SigNoz) reachable for observability exports
- [ ] Sufficient disk space for parse cache (est. 100MB per 10,000 files)
- [ ] Sufficient memory (500MB per 1,000 files)
- [ ] CPU cores available for parallel workers (4 recommended)

---

## Deployment Strategy

### Option 1: Gradual Rollout (Recommended)

Enable features incrementally over several hours/days:

**Timeline**:
- **Hour 0**: Deploy code with all features OFF
- **Hour 1**: Enable parse cache only
- **Hour 3**: Enable batching
- **Hour 5**: Enable Neo4j batching
- **Hour 7**: Enable parallel workers
- **Day 2**: Full monitoring review

**Benefits**:
- Low risk
- Easy to identify issues
- Can rollback individual features

---

### Option 2: Full Deployment

Enable all features immediately:

**Timeline**:
- **Minute 0**: Deploy with all features ON
- **Hour 1-24**: Intensive monitoring

**Benefits**:
- Immediate 10-15x improvement
- Faster deployment

**Risks**:
- Harder to identify specific issues
- Higher risk

**Recommended for**: Staging/test environments only

---

## Step-by-Step Deployment (Gradual)

### Step 1: Deploy Code (Features Disabled)

```bash
# Navigate to deployment directory
cd /opt/financial-lineage

# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "from src.config.feature_flags import FeatureFlags; print('OK')"
```

**Set environment variables (ALL FEATURES OFF)**:

```bash
# /etc/systemd/system/financial-lineage-ingestion.service
[Service]
Environment="FEATURE_PARSE_CACHE=false"
Environment="FEATURE_BATCHING=false"
Environment="FEATURE_NEO4J_BATCH=false"
Environment="FEATURE_PARALLEL=false"
Environment="FEATURE_METRICS=true"  # Keep metrics ON for monitoring
```

**Restart service**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart financial-lineage-ingestion
sudo systemctl status financial-lineage-ingestion
```

**Verify**:
```bash
# Check feature flags
python -c "from src.config.feature_flags import FeatureFlags; FeatureFlags.print_status()"

# Should show all OFF except metrics
```

**Monitor for 15 minutes**: Ensure baseline behavior is stable.

---

### Step 2: Enable Parse Cache

**Update environment**:
```bash
sudo vi /etc/systemd/system/financial-lineage-ingestion.service
# Change: Environment="FEATURE_PARSE_CACHE=true"

sudo systemctl daemon-reload
sudo systemctl restart financial-lineage-ingestion
```

**Verify**:
```bash
# Check cache statistics
python -m src.ingestion.parallel_file_watcher --cache-stats

# Monitor Prometheus metrics
curl http://localhost:8000/metrics | grep parse_cache
```

**Expected Results**:
- Cache hit rate: 25-40% after warmup
- Performance: 2-5x improvement

**Monitor for 1-2 hours**: Watch cache hit rates, memory usage.

**Rollback if needed**:
```bash
export FEATURE_PARSE_CACHE=false
sudo systemctl restart financial-lineage-ingestion
```

---

### Step 3: Enable Batching

**Update environment**:
```bash
sudo vi /etc/systemd/system/financial-lineage-ingestion.service
# Change: Environment="FEATURE_BATCHING=true"

sudo systemctl daemon-reload
sudo systemctl restart financial-lineage-ingestion
```

**Verify**:
```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep batch_

# Look for:
# - batch_size_histogram
# - batch_processing_duration_seconds
```

**Expected Results**:
- Event deduplication: 25% reduction
- Performance: Additional 2-3x improvement

**Monitor for 1-2 hours**: Watch batch sizes, deduplication rates.

**Rollback if needed**:
```bash
export FEATURE_BATCHING=false
sudo systemctl restart financial-lineage-ingestion
```

---

### Step 4: Enable Neo4j Batching

**Update environment**:
```bash
sudo vi /etc/systemd/system/financial-lineage-ingestion.service
# Change: Environment="FEATURE_NEO4J_BATCH=true"

sudo systemctl daemon-reload
sudo systemctl restart financial-lineage-ingestion
```

**Verify**:
```bash
# Monitor Neo4j connection
# Check for batch operations in Neo4j logs

# Prometheus metrics
curl http://localhost:8000/metrics | grep neo4j_batch
```

**Expected Results**:
- Neo4j transaction reduction: 100x (1 per entity → 100 per batch)
- Performance: Additional 5-10x improvement

**Monitor for 2-4 hours**: Watch Neo4j CPU/memory, transaction logs, failed ingestion log.

**Rollback if needed**:
```bash
export FEATURE_NEO4J_BATCH=false
sudo systemctl restart financial-lineage-ingestion
```

---

### Step 5: Enable Parallel Workers

**Update environment**:
```bash
sudo vi /etc/systemd/system/financial-lineage-ingestion.service
# Change: Environment="FEATURE_PARALLEL=true"
# Optionally: Environment="INGEST_WORKERS=4"

sudo systemctl daemon-reload
sudo systemctl restart financial-lineage-ingestion
```

**Verify**:
```bash
# Check worker pool
curl http://localhost:8000/metrics | grep active_workers

# Monitor CPU usage
top -p $(pgrep -f "parallel_file_watcher")
```

**Expected Results**:
- Active workers: 4 (or configured value)
- Performance: Additional 3-5x improvement
- **Total improvement: 10-15x over baseline**

**Monitor for 4-8 hours**: Watch CPU, memory, queue size, processing rates.

**Rollback if needed**:
```bash
export FEATURE_PARALLEL=false
sudo systemctl restart financial-lineage-ingestion
```

---

## Post-Deployment Verification

### Performance Validation

**Run benchmark**:
```bash
pytest tests/performance/test_ingestion_benchmark.py -v
```

**Check Prometheus metrics**:
```promql
# Throughput (should be 10-15x baseline)
rate(files_processed_total[5m]) * 60

# Cache hit rate (should be 25-40%)
rate(parse_cache_hit_total[5m]) / (rate(parse_cache_hit_total[5m]) + rate(parse_cache_miss_total[5m]))

# Batch processing duration (p95 should be < 2s)
histogram_quantile(0.95, rate(batch_processing_duration_seconds_bucket[5m]))

# Worker utilization
active_workers  # Should match configured workers

# Error rate (should be < 1%)
rate(files_failed_total[5m]) / rate(files_processed_total[5m])
```

**Expected Metrics**:
| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Throughput improvement | 10-15x | 8-20x |
| Cache hit rate | 25-40% | 20-50% |
| p95 batch duration | < 2s | < 5s |
| Error rate | < 1% | < 5% |
| Memory usage | < 500MB/1000 files | < 1GB/1000 files |

---

### Health Checks

**Service health**:
```bash
systemctl status financial-lineage-ingestion
# Should show: active (running)
```

**Application health**:
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

**Metrics endpoint**:
```bash
curl http://localhost:8000/metrics | head -n 20
# Should return Prometheus metrics
```

**Feature flags**:
```bash
python -c "from src.config.feature_flags import FeatureFlags; FeatureFlags.print_status()"
# Should show all features ENABLED
```

---

## SigNoz Observability Setup

**Start SigNoz**:
1. Run `docker compose -f docker-compose.signoz.yml up -d`
2. Open `http://localhost:3301`
3. Set OTLP env vars for the API process:
   - `OTEL_ENABLED=true`
   - `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`
   - `OTEL_SERVICE_NAME=financial-lineage-backend`

**Key views to monitor**:
- Service traces for API latency and errors
- Logs for ingestion pipeline stages and failures
- Metrics for throughput, cache hit rate, and worker utilization

**Set up alerts (optional)**:
- High error rate
- High p95 latency
- Ingestion throughput drop

---

## Rollback Procedures

See [ROLLBACK_PROCEDURES.md](ROLLBACK_PROCEDURES.md) for detailed rollback instructions.

**Quick rollback** (< 5 minutes):
```bash
# Disable all optimizations
export FEATURE_PARSE_CACHE=false
export FEATURE_BATCHING=false
export FEATURE_NEO4J_BATCH=false
export FEATURE_PARALLEL=false

sudo systemctl restart financial-lineage-ingestion
```

---

## Troubleshooting

### Issue: High Memory Usage

**Symptoms**: Memory > 80%, OOM errors

**Solution**:
```bash
# Reduce workers
export INGEST_WORKERS=2  # Default: 4

# OR disable parallel workers
export FEATURE_PARALLEL=false

sudo systemctl restart financial-lineage-ingestion
```

---

### Issue: Cache Not Working

**Symptoms**: Cache hit rate = 0%

**Solution**:
```bash
# Check cache path exists
ls -lh data/.cache/parse_cache.db

# Clear and rebuild cache
python -m src.ingestion.parallel_file_watcher --clear-cache

# Check permissions
chmod 644 data/.cache/parse_cache.db
```

---

### Issue: Neo4j Timeouts

**Symptoms**: `ServiceUnavailable: Connection pool timeout`

**Solution**:
```bash
# Reduce batch size
export NEO4J_BATCH_SIZE=25  # Default: 100

# OR disable Neo4j batching
export FEATURE_NEO4J_BATCH=false

sudo systemctl restart financial-lineage-ingestion
```

---

## Success Criteria

Deployment is considered successful when:

- ✅ All feature flags enabled
- ✅ Throughput improvement 10-15x (or within 8-20x range)
- ✅ Cache hit rate 25-40%
- ✅ Error rate < 1%
- ✅ No memory/CPU issues
- ✅ Prometheus metrics collecting correctly
- ✅ SigNoz UI operational
- ✅ 24 hours of stable operation

---

## Communication Template

### Deployment Start Email

```
Subject: [DEPLOYMENT] Financial Lineage Ingestion Pipeline Optimization - Starting

Team,

We are beginning the gradual deployment of the optimized ingestion pipeline.

Timeline:
- Now: Code deployed (features disabled)
- +1hr: Enable parse cache
- +3hr: Enable batching
- +5hr: Enable Neo4j batching
- +7hr: Enable parallel workers

Expected Impact:
- 10-15x throughput improvement
- Reduced processing time: 10 min → 1 min for 1000 files

Monitoring:
- SigNoz: http://localhost:3301
- Metrics: http://localhost:8000/metrics

Rollback: < 5 minutes if needed

Contact: oncall@example.com

Thanks,
DevOps Team
```

---

### Deployment Complete Email

```
Subject: [COMPLETE] Financial Lineage Ingestion Pipeline Optimization

Team,

The optimized ingestion pipeline has been successfully deployed.

Results:
- Throughput improvement: 12x (target: 10-15x) ✅
- Cache hit rate: 32% (target: 25-40%) ✅
- Error rate: 0.1% (target: <1%) ✅
- 24 hours stable operation ✅

All optimizations enabled and performing as expected.

Monitoring continues via SigNoz UI.

Thanks,
DevOps Team
```

---

## Document History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2025-12-30 | Initial release | Claude Code |

---

**Next Steps**:
- Monitor for 7 days
- Collect performance data
- Optimize based on production metrics
- Update runbooks if needed
