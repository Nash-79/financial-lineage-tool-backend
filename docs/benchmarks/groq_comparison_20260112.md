# Groq LLM Quality Comparison

**Date**: 2026-01-12
**Provider**: groq
**Models Tested**: 3
**Dataset**: 20 SQL lineage Q&A pairs

---

## Summary

| Model | Accuracy | Citation | Halluc. | Complete | Latency | Grade |
|-------|----------|----------|---------|----------|---------|-------|
| llama-3.1-70b-versatile | 0.000 | 0.000 | 0.000 | 0.000 | 0ms | D |
| llama-3.1-8b-instant | 0.242 | 0.944 | 0.775 | 0.175 | 670ms | D |
| mixtral-8x7b-32768 | 0.000 | 0.000 | 0.000 | 0.000 | 0ms | D |


---

## [WINNER] Recommendation

**Best Groq Model**: `llama-3.1-8b-instant`

**Why?**
- Accuracy: 0.242
- Citation Quality: 0.944
- Hallucination Rate: 0.775
- Completeness: 0.175

**Description**: Llama 3.1 8B (fastest)

---

## Detailed Results by Category


### llama-3.1-70b-versatile

| Category | Accuracy | Completeness |
|----------|----------|--------------|

### llama-3.1-8b-instant

| Category | Accuracy | Completeness |
|----------|----------|--------------|
| data_flow | 0.187 | 0.123 |
| join_analysis | 0.251 | 0.107 |
| schema_lookup | 0.293 | 0.400 |
| transformation_logic | 0.236 | 0.000 |

### mixtral-8x7b-32768

| Category | Accuracy | Completeness |
|----------|----------|--------------|
