# LLM Quality Benchmarking Methodology

## Overview

This document describes the methodology for benchmarking Large Language Model (LLM) quality in the Financial Lineage Tool RAG pipeline. The goal is to measure answer quality for SQL lineage questions and make data-driven decisions about model selection.

---

## Why Benchmark LLMs?

LLM quality directly impacts user trust and accuracy:

| Poor LLM Quality → | Impact |
|-------------------|--------|
| Wrong answers | Users lose trust in system |
| Missing information | Incomplete lineage analysis |
| Hallucinations | False SQL relationships suggested |
| No citations | Can't verify claims |

**Our Requirements:**
- **Accuracy > 0.8** - Mentions all required entities and concepts
- **Citation Quality > 0.9** - Backs claims with code/file references
- **Hallucination Rate < 0.1** - Avoids inventing facts
- **Completeness > 0.9** - Covers all relevant information
- **Latency < 3000ms** - Fast enough for interactive queries

---

## Ground Truth Q&A Dataset

### Design Principles

1. **SQL-domain specific** - Questions about joins, schemas, data flow
2. **Realistic scenarios** - Actual questions users ask
3. **Ideal answers provided** - What a perfect response looks like
4. **Required entities/concepts** - What must be mentioned for correctness

### Dataset Structure

**Location**: `tests/benchmarks/llm_ground_truth.json`

**Format**:
```json
{
  "qa_pairs": [
    {
      "id": "join_qa_001",
      "question": "What tables does customer_orders join with?",
      "ideal_answer": "The customer_orders table joins with customers (on customer_id) and products (on product_id)...",
      "required_entities": ["customer_orders", "customers", "products"],
      "required_concepts": ["join", "customer_id", "product_id"],
      "context_files": ["sql/analytics/order_analytics.sql"],
      "category": "join_analysis",
      "difficulty": "easy"
    }
  ]
}
```

### Categories

| Category | Description | Count | Example |
|----------|-------------|-------|---------|
| **Join Analysis** | Multi-table relationships | 5 | "What tables does X join with?" |
| **Schema Lookup** | Table/column discovery | 5 | "What columns are in users table?" |
| **Data Flow** | Upstream/downstream lineage | 5 | "Trace the pipeline from X to Y" |
| **Transformation Logic** | CTEs, window functions, aggregations | 5 | "How does the running total work?" |

**Total**: 20 Q&A pairs

### Difficulty Levels

- **Easy** (30%) - Single concept, direct answer
- **Medium** (50%) - Multiple entities, requires synthesis
- **Hard** (20%) - Complex queries, deep understanding

---

## Metrics

### 1. Accuracy (0-1 scale)

**Definition**: Does the answer mention required entities and concepts?

**Calculation**:
```python
entity_score = (entities_mentioned / required_entities)
concept_score = (concepts_mentioned / required_concepts)
accuracy = 0.6 * entity_score + 0.4 * concept_score
```

**Interpretation**:
- `0.8-1.0` = Excellent - All key information present
- `0.6-0.8` = Good - Most information present
- `0.4-0.6` = Acceptable - Some missing information
- `< 0.4` = Poor - Critical information missing

**Target**: > 0.8

**Why it matters**: Users need correct, complete answers to understand lineage.

---

### 2. Citation Quality (0 or 1)

**Definition**: Does answer include code snippets or file references?

**Binary Score**:
```python
has_code = "```" in answer
has_file = any(context_file in answer)
citation_score = 1.0 if (has_code or has_file) else 0.0
```

**Interpretation**:
- `1.0` = Answer cites sources (code blocks or file paths)
- `0.0` = Answer makes claims without evidence

**Target**: > 0.9 (90% of answers should cite sources)

**Why it matters**: Users need to verify claims. Code snippets build trust.

---

### 3. Hallucination Rate (0-1, lower is better)

**Definition**: Does answer mention entities not in context or ground truth?

**Heuristic Detection**:
```python
mentioned_tables = extract_sql_identifiers(answer)
allowed_tables = ground_truth_entities + context_entities
hallucinated = [t for t in mentioned_tables if t not in allowed]
hallucination_rate = len(hallucinated) / len(mentioned_tables)
```

**Interpretation**:
- `< 0.05` = Excellent - Rarely invents facts
- `0.05-0.10` = Good - Occasional hallucinations
- `0.10-0.20` = Acceptable - Some invented facts
- `> 0.20` = Poor - Frequently hallucinates

**Target**: < 0.1

**Limitations**:
- Heuristic-based (not perfect)
- May false-positive on valid SQL keywords
- Manual review recommended for critical cases

**Why it matters**: Hallucinations mislead users about actual lineage.

---

### 4. Completeness (0-1 scale)

**Definition**: What fraction of required entities are mentioned?

**Calculation**:
```python
mentioned = sum(1 for entity in required if entity in answer)
completeness = mentioned / len(required_entities)
```

**Interpretation**:
- `1.0` = Perfect - All required entities mentioned
- `0.8-1.0` = Good - Most entities covered
- `0.6-0.8` = Acceptable - Some entities missing
- `< 0.6` = Poor - Many entities missing

**Target**: > 0.9

**Why it matters**: Incomplete answers leave users with unanswered questions.

---

### 5. Latency

**Measurements**:
- **TTFT** (Time to First Token) - Perceived responsiveness
- **Total Latency** - Full generation time

**Targets**:
- TTFT < 500ms (user perceives as instant)
- Total < 3000ms (acceptable for complex queries)

**Why it matters**: Interactive UX requires fast responses.

---

## Methodology

### Test Execution

1. **Load Q&A Dataset**: Parse `llm_ground_truth.json`
2. **For each question**:
   - Retrieve RAG context (top-5 code chunks via vector search)
   - Generate answer using test LLM
   - Calculate metrics (accuracy, citation, hallucination, completeness)
   - Measure latency (TTFT + total)
3. **Aggregate**: Average metrics across all questions
4. **Grade**: A (>0.9), B (0.8-0.9), C (0.7-0.8), D (<0.7)
5. **Report**: Generate markdown with results and recommendation

### RAG Context

**Important**: Tests use actual RAG context (vector search results), not zero-shot.

This ensures:
- Realistic evaluation (production uses RAG)
- Fair comparison (all models get same context)
- Citation validation possible (files are in context)

### Model Selection

**Free Models Only** - No paid APIs:

| Provider | Models | Why |
|----------|--------|-----|
| **Ollama** | llama3.1:8b, llama3.1:8b-q4 | Local, privacy, no API costs |
| **Groq** | llama-3.1-70b, llama-3.1-8b, mixtral-8x7b | Fast inference, free tier |
| **OpenRouter** | llama-3.1-8b:free, gemma-2-9b:free | Backup, diverse models |

**Total**: 7 models tested

---

## Grading System

### Overall Grade Calculation

**Weighted Score**:
```
grade_score = (
  accuracy * 0.35 +
  citation_quality * 0.20 +
  (1 - hallucination_rate) * 0.25 +
  completeness * 0.20
)
```

**Letter Grades**:
- **A** (0.9-1.0) = Excellent ✨ - Production ready
- **B** (0.8-0.9) = Good ✅ - Acceptable for production
- **C** (0.7-0.8) = Acceptable ⚠️ - Use with caution
- **D** (<0.7) = Poor ❌ - Do not use

### Why These Weights?

- **Accuracy (35%)** - Most important: wrong answer = wrong lineage
- **Hallucination (25%)** - Critical: false info damages trust
- **Citation (20%)** - Important: users need to verify
- **Completeness (20%)** - Important: partial info frustrating

---

## Running Benchmarks

### Prerequisites

1. **Pull LLM models**:
   ```bash
   ollama pull llama3.1:8b
   ollama pull llama3.1:8b-q4
   ```

2. **API keys** (for cloud models):
   ```bash
   export GROQ_API_KEY="your-key"
   export OPENROUTER_API_KEY="your-key"
   ```

3. **Index test data**: Ensure vector DB has SQL files

### CLI Usage

**List available models**:
```bash
python scripts/benchmark_llms.py --list-models
```

**Test single model**:
```bash
python scripts/benchmark_llms.py --model llama3.1:8b
```

**Compare all Ollama models**:
```bash
python scripts/benchmark_llms.py --provider ollama
```

**Comprehensive comparison** (all providers):
```bash
python scripts/benchmark_llms.py --compare-all
```

### Output

- **Results JSON**: `docs/benchmarks/llm_results/{provider}_{model}_results.json`
- **Provider Report**: `docs/benchmarks/{provider}_comparison_YYYYMMDD.md`
- **Comprehensive Report**: `docs/benchmarks/llm_comprehensive_YYYYMMDD.md`

---

## Interpreting Results

### Excellent Results ✨

```
✅ Accuracy: 0.90        → Nearly perfect answers
✅ Citation: 1.00        → Always cites sources
✅ Hallucination: 0.02   → Rarely invents facts
✅ Completeness: 0.95    → Comprehensive coverage
✅ Latency: 800ms        → Very fast
```

**Grade**: A (Excellent)  
**Action**: ✅ Deploy to production as primary model

### Good Results ✅

```
✅ Accuracy: 0.85        → Mostly correct
✅ Citation: 0.90        → Usually cites sources
⚠️ Hallucination: 0.08   → Occasional hallucinations
✅ Completeness: 0.88    → Good coverage
✅ Latency: 1200ms       → Acceptable
```

**Grade**: B (Good)  
**Action**: ✅ Acceptable for production, monitor hallucinations

### Acceptable Results ⚠️

```
⚠️ Accuracy: 0.75        → Some errors
⚠️ Citation: 0.80        → Sometimes missing citations
⚠️ Hallucination: 0.12   → Noticeable hallucinations
⚠️ Completeness: 0.82    → Missing some info
✅ Latency: 1500ms       → OK
```

**Grade**: C (Acceptable)  
**Action**: 🔍 Use with caution, implement validation layer

### Poor Results ❌

```
❌ Accuracy: 0.60        → Frequent errors
❌ Citation: 0.60        → Rarely cites sources
❌ Hallucination: 0.25   → Frequent hallucinations
❌ Completeness: 0.70    → Often incomplete
⚠️ Latency: 2500ms       → Slow
```

**Grade**: D (Poor)  
**Action**: ❌ Do not use - find alternative model

---

## Model Selection Criteria

### Decision Matrix

| Factor | Weight | Importance |
|--------|--------|------------|
| Accuracy | 35% | Wrong answers break trust |
| Hallucination | 25% | False info is dangerous |
| Citation | 20% | Users need verification |
| Completeness | 20% | Partial info frustrating |

### Trade-offs

**Accuracy vs Speed**:
- 70B model: +15% accuracy, +3x latency
- 8B model: -15% accuracy, 3x faster
- **Rule**: Accept 2x latency for 10%+ accuracy gain

**Cloud vs Local**:
- Cloud (Groq): Better accuracy, requires internet, privacy concerns
- Local (Ollama): Privacy, works offline, lower accuracy
- **Rule**: Use cloud for public data, local for sensitive data

**Cost Considerations**:
- All benchmarked models are FREE
- Groq: 30 req/min limit (acceptable for most use cases)
- Ollama: No limits, but requires GPU

---

## Production Deployment Strategy

### Recommended Fallback Chain

Based on benchmark results:

```python
# 1. Primary: Best cloud model (usually Groq llama-3.1-70b)
# 2. Fallback: Privacy (Ollama llama3.1:8b for sensitive queries)
# 3. Backup: Speed (Groq llama-3.1-8b-instant for high load)
```

**Configuration**:
```python
INFERENCE_STRATEGY = {
  "primary": "groq:llama-3.1-70b",
  "fallback": "ollama:llama3.1:8b",
  "backup": "groq:llama-3.1-8b-instant"
}
```

### Circuit Breaker Integration

- **Rate limit hit** → Switch to fallback
- **Network error** → Switch to local model
- **High latency** (>5s) → Switch to faster model

---

## Limitations

1. **Small dataset** (20 Q&A) - Not statistically robust
   - **Mitigation**: Expand to 50+ over time

2. **Heuristic hallucination** - Not perfect detection
   - **Mitigation**: Manual review of failed cases

3. **No fine-tuning** - Tests base models only
   - **Future**: Fine-tune on SQL domain

4. **Static evaluation** - Doesn't account for user preferences
   - **Future**: A/B test in production

---

## Future Improvements

1. **Automatic evaluation** - Use LLM-as-judge (GPT-4 scores answers)
2. **Fine-tuning** - Train custom model on SQL lineage data
3. **Prompt optimization** - A/B test different prompt templates
4. **Real-user validation** - Collect thumbs up/down feedback
5. **Adversarial testing** - Edge cases, malicious inputs

---

## References

- [Eval Harness](https://github.com/EleutherAI/lm-evaluation-harness) - LLM evaluation framework
- [RAGAS](https://github.com/explodinggradients/ragas) - RAG evaluation metrics
- [Groq API Docs](https://console.groq.com/docs)
- [OpenRouter Docs](https://openrouter.ai/docs)

---

## Questions?

For questions about this methodology, contact the maintainers or open an issue on GitHub.
