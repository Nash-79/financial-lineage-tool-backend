"""
LLM quality benchmarking for SQL lineage question answering.

Tests LLM models against a ground truth Q&A dataset to measure:
- Accuracy - Does it mention required entities and concepts?
- Citation Quality - Does it back claims with code/file references?
- Hallucination Rate - Does it invent facts not in context?
- Completeness - Does it cover all required information?
- Latency - Time to first token (TTFT) and total response time
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, Callable

import pytest


class LLMBenchmark:
    """Benchmark LLM quality for SQL lineage Q&A."""

    def __init__(self, ground_truth_path: Path):
        """Initialize benchmark with ground truth Q&A dataset.

        Args:
            ground_truth_path: Path to ground truth JSON file
        """
        with open(ground_truth_path) as f:
            data = json.load(f)

        self.qa_pairs = data["qa_pairs"]
        self.metadata = data.get("metadata", {})

    def run_benchmark(
        self,
        llm_function: Callable,
        search_function: Callable,
        model_name: str = "unknown",
        provider: str = "unknown",
    ) -> Dict:
        """Run full LLM quality benchmark.

        Args:
            llm_function: Function that takes (question: str, context: list) and
                         returns answer string
            search_function: Function that takes (query: str, limit: int) and returns
                            list of context chunks
            model_name: Name of LLM model being tested
            provider: Provider (ollama, groq, openrouter)

        Returns:
            Dictionary with all metrics
        """
        results = {
            "model": model_name,
            "provider": provider,
            "accuracy": 0.0,
            "citation_quality": 0.0,
            "hallucination_rate": 0.0,
            "completeness": 0.0,
            "ttft_ms": [],
            "total_latency_ms": [],
            "by_category": {},
            "by_difficulty": {},
            "failed_questions": [],
        }

        for qa in self.qa_pairs:
            question = qa["question"]

            # Get RAG context
            context = search_function(question, limit=5)

            # Generate answer with timing
            start = time.time()
            try:
                answer = llm_function(question, context)
                total_latency = (time.time() - start) * 1000

                # Calculate metrics
                accuracy = self._score_accuracy(answer, qa)
                citation = self._score_citations(answer, context)
                hallucination = self._detect_hallucination(answer, qa, context)
                completeness = self._score_completeness(answer, qa)

                results["accuracy"] += accuracy
                results["citation_quality"] += citation
                results["hallucination_rate"] += hallucination
                results["completeness"] += completeness
                results["total_latency_ms"].append(total_latency)

                # Track by category
                category = qa["category"]
                if category not in results["by_category"]:
                    results["by_category"][category] = {
                        "count": 0,
                        "accuracy": 0.0,
                        "completeness": 0.0,
                    }
                results["by_category"][category]["count"] += 1
                results["by_category"][category]["accuracy"] += accuracy
                results["by_category"][category]["completeness"] += completeness

            except Exception as e:
                results["failed_questions"].append(
                    {"id": qa["id"], "question": question, "error": str(e)}
                )

        # Average metrics
        num_success = len(self.qa_pairs) - len(results["failed_questions"])
        if num_success > 0:
            results["accuracy"] /= num_success
            results["citation_quality"] /= num_success
            results["hallucination_rate"] /= num_success
            results["completeness"] /= num_success

            if results["total_latency_ms"]:
                results["avg_latency_ms"] = sum(results["total_latency_ms"]) / len(
                    results["total_latency_ms"]
                )

            # Average by category
            for category, data in results["by_category"].items():
                if data["count"] > 0:
                    data["accuracy"] /= data["count"]
                    data["completeness"] /= data["count"]

        return results

    def _score_accuracy(self, answer: str, qa_data: dict) -> float:
        """Calculate answer accuracy based on required entities and concepts.

        Args:
            answer: LLM generated answer
            qa_data: Ground truth Q&A data

        Returns:
            Accuracy score (0.0 to 1.0)
        """
        answer_lower = answer.lower()

        # Check required entities mentioned
        entities_found = sum(
            1
            for entity in qa_data["required_entities"]
            if entity.lower() in answer_lower
        )
        entity_score = (
            entities_found / len(qa_data["required_entities"])
            if qa_data["required_entities"]
            else 0.0
        )

        # Check required concepts mentioned
        concepts_found = sum(
            1
            for concept in qa_data["required_concepts"]
            if concept.lower() in answer_lower
        )
        concept_score = (
            concepts_found / len(qa_data["required_concepts"])
            if qa_data["required_concepts"]
            else 0.0
        )

        # Weighted average (entities 60%, concepts 40%)
        return 0.6 * entity_score + 0.4 * concept_score

    def _score_citations(self, answer: str, context: list) -> float:
        """Calculate citation quality (does answer reference sources?).

        Args:
            answer: LLM generated answer
            context: List of context chunks

        Returns:
            Citation score (0.0 or 1.0)
        """
        # Check for code blocks
        has_code_block = "```" in answer

        # Check for file references
        has_file_ref = False
        for ctx in context:
            file_path = ""
            if isinstance(ctx, dict):
                if "payload" in ctx and "file_path" in ctx["payload"]:
                    file_path = ctx["payload"]["file_path"]
                elif "file_path" in ctx:
                    file_path = ctx["file_path"]

            if file_path and file_path in answer:
                has_file_ref = True
                break

        # Citation present if has code OR file reference
        return 1.0 if (has_code_block or has_file_ref) else 0.0

    def _detect_hallucination(self, answer: str, qa_data: dict, context: list) -> float:
        """Detect hallucinations (facts not in context).

        This is a simplified heuristic: checks if answer mentions entities
        not in the required list or context.

        Args:
            answer: LLM generated answer
            qa_data: Ground truth Q&A data
            context: List of context chunks

        Returns:
            Hallucination rate (0.0 to 1.0, lower is better)
        """
        # Extract potential table names from answer (basic heuristic)
        # Matches SQL-style identifiers
        mentioned_tables = set(re.findall(r"\b[a-z_]{3,}\b", answer.lower()))

        # Get allowed entities from ground truth
        allowed_entities = set(e.lower() for e in qa_data["required_entities"])

        # Get entities from context
        context_entities = set()
        for ctx in context:
            if isinstance(ctx, dict):
                content = ctx.get("payload", {}).get("content", "")
                if content:
                    # Extract table names from SQL (FROM, JOIN clauses)
                    context_entities.update(re.findall(r"FROM\s+(\w+)", content, re.I))
                    context_entities.update(re.findall(r"JOIN\s+(\w+)", content, re.I))

        context_entities = set(e.lower() for e in context_entities)

        # Combine allowed sets
        allowed = allowed_entities | context_entities

        # Find hallucinated entities (mentioned but not allowed)
        # Filter out common SQL keywords
        sql_keywords = {
            "select",
            "from",
            "where",
            "join",
            "left",
            "right",
            "inner",
            "outer",
            "group",
            "order",
            "having",
            "limit",
            "offset",
            "and",
            "or",
            "not",
            "null",
            "true",
            "false",
            "case",
            "when",
            "then",
            "else",
            "end",
            "with",
            "as",
            "on",
            "using",
            "into",
            "values",
        }

        hallucinated = [
            t
            for t in mentioned_tables
            if t not in allowed and t not in sql_keywords and len(t) > 3
        ]

        if len(mentioned_tables) == 0:
            return 0.0

        return len(hallucinated) / max(len(mentioned_tables), 1)

    def _score_completeness(self, answer: str, qa_data: dict) -> float:
        """Calculate completeness (coverage of required entities).

        Args:
            answer: LLM generated answer
            qa_data: Ground truth Q&A data

        Returns:
            Completeness score (0.0 to 1.0)
        """
        answer_lower = answer.lower()

        required = qa_data["required_entities"]
        if not required:
            return 1.0

        found = sum(1 for entity in required if entity.lower() in answer_lower)

        return found / len(required)

    def generate_report(self, results: Dict) -> str:
        """Generate markdown report from benchmark results.

        Args:
            results: Benchmark results dictionary

        Returns:
            Markdown formatted report
        """
        report = f"""# LLM Quality Benchmark Results

**Model**: {results['model']}
**Provider**: {results['provider']}
**Date**: {time.strftime('%Y-%m-%d')}
**Questions**: {len(self.qa_pairs)}
**Failed**: {len(results.get('failed_questions', []))}

## Summary Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Accuracy | {results['accuracy']:.3f} | > 0.80 |
| Citation Quality | {results['citation_quality']:.3f} | > 0.90 |
| Hallucination Rate | {results['hallucination_rate']:.3f} | < 0.10 |
| Completeness | {results['completeness']:.3f} | > 0.90 |
| Avg Latency | {results.get('avg_latency_ms', 0):.0f}ms | < 3000ms |

## Performance Grade

"""
        # Calculate overall grade
        grade_score = (
            results["accuracy"] * 0.35
            + results["citation_quality"] * 0.20
            + (1 - results["hallucination_rate"]) * 0.25
            + results["completeness"] * 0.20
        )

        if grade_score >= 0.9:
            grade = "A (Excellent)"
        elif grade_score >= 0.8:
            grade = "B (Good)"
        elif grade_score >= 0.7:
            grade = "C (Acceptable)"
        else:
            grade = "D (Poor)"

        report += f"**Overall Grade**: {grade} ({grade_score:.3f})\n\n"

        # By category
        report += "## Results by Category\n\n| Category | Accuracy | Completeness | Count |\n|----------|----------|--------------|-------|\n"
        for category, data in sorted(results["by_category"].items()):
            report += f"| {category} | {data['accuracy']:.3f} | {data['completeness']:.3f} | {data['count']} |\n"

        # Failed questions
        if results.get("failed_questions"):
            report += "\n## Failed Questions\n\n"
            for failed in results["failed_questions"]:
                report += f"- **{failed['id']}**: {failed['question']}\n"
                report += f"  - Error: {failed['error']}\n"

        return report


# ============== Tests ==============


def test_benchmark_initialization():
    """Test that benchmark can load ground truth."""
    gt_path = Path(__file__).parent / "llm_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = LLMBenchmark(gt_path)
    assert len(benchmark.qa_pairs) > 0
    assert "metadata" in dir(benchmark)


def test_accuracy_scoring():
    """Test accuracy calculation logic."""
    gt_path = Path(__file__).parent / "llm_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = LLMBenchmark(gt_path)

    qa = {
        "required_entities": ["users", "orders"],
        "required_concepts": ["join", "foreign key"],
    }

    # Perfect answer
    answer = "The users table joins with orders on the foreign key user_id"
    score = benchmark._score_accuracy(answer, qa)
    assert score == 1.0

    # Partial answer (missing concepts)
    answer = "The users and orders tables are related"
    score = benchmark._score_accuracy(answer, qa)
    assert 0.5 < score < 1.0

    # Poor answer
    answer = "There are database tables"
    score = benchmark._score_accuracy(answer, qa)
    assert score < 0.5


def test_citation_detection():
    """Test citation quality scoring."""
    gt_path = Path(__file__).parent / "llm_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = LLMBenchmark(gt_path)

    # With code block
    answer = "Here's the query:\n```sql\nSELECT * FROM users\n```"
    assert benchmark._score_citations(answer, []) == 1.0

    # With file reference
    answer = "See sql/schema/users.sql for details"
    context = [{"payload": {"file_path": "sql/schema/users.sql"}}]
    assert benchmark._score_citations(answer, context) == 1.0

    # No citations
    answer = "The users table exists"
    assert benchmark._score_citations(answer, []) == 0.0


def test_hallucination_detection():
    """Test hallucination detection logic."""
    gt_path = Path(__file__).parent / "llm_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = LLMBenchmark(gt_path)

    qa = {"required_entities": ["users", "orders"]}
    context = [{"payload": {"content": "FROM users JOIN orders"}}]

    # No hallucination (only mentions allowed entities)
    answer = "The users table joins with orders"
    rate = benchmark._detect_hallucination(answer, qa, context)
    assert rate == 0.0

    # Hallucination (mentions non-existent table)
    answer = "The users, orders, and fictional_table are related"
    rate = benchmark._detect_hallucination(answer, qa, context)
    assert rate > 0.0


def test_completeness_scoring():
    """Test completeness calculation."""
    gt_path = Path(__file__).parent / "llm_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = LLMBenchmark(gt_path)

    qa = {"required_entities": ["users", "orders", "payments"]}

    # Complete answer
    answer = "The system has users, orders, and payments tables"
    assert benchmark._score_completeness(answer, qa) == 1.0

    # Partial answer
    answer = "The users and orders tables exist"
    assert benchmark._score_completeness(answer, qa) == pytest.approx(2 / 3)

    # Incomplete answer
    answer = "The users table is present"
    assert benchmark._score_completeness(answer, qa) == pytest.approx(1 / 3)
