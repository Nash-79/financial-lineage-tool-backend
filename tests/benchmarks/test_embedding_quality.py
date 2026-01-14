"""
Embedding quality benchmarking for SQL lineage retrieval.

Tests embedding models against a ground truth dataset to measure:
- Precision@k - Relevance of top-k results
- Recall@k - Coverage of relevant chunks in top-k
- MRR - Mean Reciprocal Rank of first relevant result
- nDCG@k - Normalized Discounted Cumulative Gain (ranking quality)
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Set
import math

import pytest


class EmbeddingBenchmark:
    """Benchmark embedding models for SQL lineage retrieval quality."""

    def __init__(self, ground_truth_path: Path):
        """Initialize benchmark with ground truth dataset.

        Args:
            ground_truth_path: Path to ground truth JSON file
        """
        with open(ground_truth_path) as f:
            data = json.load(f)

        self.queries = data["queries"]
        self.metadata = data.get("metadata", {})

    def run_benchmark(
        self,
        search_function,
        k_values: List[int] = [1, 3, 5, 10],
        embedding_model: str = "nomic-embed-text",
    ) -> Dict:
        """Run full benchmark suite.

        Args:
            search_function: Function that takes (query: str, limit: int) and returns
                            list of dicts with 'file_path' or 'payload.file_path'
            k_values: List of k values to evaluate (e.g., [1, 3, 5, 10])
            embedding_model: Name of embedding model being tested

        Returns:
            Dictionary with all metrics
        """
        results = {
            "model": embedding_model,
            "precision_at_k": {k: 0.0 for k in k_values},
            "recall_at_k": {k: 0.0 for k in k_values},
            "mrr": 0.0,
            "ndcg_at_k": {k: 0.0 for k in k_values},
            "latency_ms": [],
            "by_category": {},
            "by_difficulty": {},
        }

        for query_data in self.queries:
            query = query_data["query"]
            relevant_set = set(query_data["relevant_chunks"])

            # Time the search
            start = time.time()
            retrieved = search_function(query, limit=max(k_values))
            latency_ms = (time.time() - start) * 1000
            results["latency_ms"].append(latency_ms)

            # Extract file paths from results
            retrieved_paths = self._extract_paths(retrieved)

            # Calculate metrics for each k
            for k in k_values:
                top_k = retrieved_paths[:k]

                # Precision@k
                precision = self._precision_at_k(top_k, relevant_set)
                results["precision_at_k"][k] += precision

                # Recall@k
                recall = self._recall_at_k(top_k, relevant_set)
                results["recall_at_k"][k] += recall

                # nDCG@k
                ndcg = self._ndcg_at_k(retrieved_paths, relevant_set, k)
                results["ndcg_at_k"][k] += ndcg

            # MRR (only needs one calculation per query)
            mrr = self._reciprocal_rank(retrieved_paths, relevant_set)
            results["mrr"] += mrr

            # Track by category
            category = query_data["category"]
            if category not in results["by_category"]:
                results["by_category"][category] = {"count": 0, "precision_at_5": 0.0}
            results["by_category"][category]["count"] += 1
            results["by_category"][category]["precision_at_5"] += self._precision_at_k(
                retrieved_paths[:5], relevant_set
            )

        # Average all metrics
        num_queries = len(self.queries)
        for k in k_values:
            results["precision_at_k"][k] /= num_queries
            results["recall_at_k"][k] /= num_queries
            results["ndcg_at_k"][k] /= num_queries
        results["mrr"] /= num_queries
        results["avg_latency_ms"] = sum(results["latency_ms"]) / len(
            results["latency_ms"]
        )

        # Average by category
        for category, data in results["by_category"].items():
            data["precision_at_5"] /= data["count"]

        return results

    def _extract_paths(self, results: List[Dict]) -> List[str]:
        """Extract file paths from search results.

        Handles both formats:
        - {'payload': {'file_path': '...'}}
        - {'file_path': '...'}
        """
        paths = []
        for r in results:
            if isinstance(r, dict):
                if "payload" in r and "file_path" in r["payload"]:
                    paths.append(r["payload"]["file_path"])
                elif "file_path" in r:
                    paths.append(r["file_path"])
        return paths

    def _precision_at_k(self, retrieved: List[str], relevant: Set[str]) -> float:
        """Calculate Precision@k.

        Precision@k = (# relevant in top k) / k

        Args:
            retrieved: List of retrieved file paths (top k)
            relevant: Set of relevant file paths

        Returns:
            Precision score (0.0 to 1.0)
        """
        if not retrieved:
            return 0.0

        relevant_count = sum(
            1 for path in retrieved if self._is_relevant(path, relevant)
        )
        return relevant_count / len(retrieved)

    def _recall_at_k(self, retrieved: List[str], relevant: Set[str]) -> float:
        """Calculate Recall@k.

        Recall@k = (# relevant in top k) / (total # relevant)

        Args:
            retrieved: List of retrieved file paths (top k)
            relevant: Set of relevant file paths

        Returns:
            Recall score (0.0 to 1.0)
        """
        if not relevant:
            return 0.0

        relevant_count = sum(
            1 for path in retrieved if self._is_relevant(path, relevant)
        )
        return relevant_count / len(relevant)

    def _reciprocal_rank(self, retrieved: List[str], relevant: Set[str]) -> float:
        """Calculate Reciprocal Rank.

        RR = 1 / (position of first relevant result)

        Args:
            retrieved: List of retrieved file paths
            relevant: Set of relevant file paths

        Returns:
            Reciprocal rank (0.0 to 1.0)
        """
        for i, path in enumerate(retrieved, start=1):
            if self._is_relevant(path, relevant):
                return 1.0 / i
        return 0.0

    def _ndcg_at_k(self, retrieved: List[str], relevant: Set[str], k: int) -> float:
        """Calculate Normalized Discounted Cumulative Gain@k.

        DCG@k = sum(rel_i / log2(i + 1)) for i in 1..k
        IDCG@k = DCG for perfect ranking
        nDCG@k = DCG@k / IDCG@k

        Args:
            retrieved: List of retrieved file paths
            relevant: Set of relevant file paths
            k: Cutoff position

        Returns:
            nDCG score (0.0 to 1.0)
        """
        # Calculate DCG
        dcg = 0.0
        for i, path in enumerate(retrieved[:k], start=1):
            rel = 1.0 if self._is_relevant(path, relevant) else 0.0
            dcg += rel / math.log2(i + 1)

        # Calculate IDCG (ideal DCG with perfect ranking)
        ideal_ranking = [1.0] * min(len(relevant), k)  # All relevant first
        idcg = sum(
            rel / math.log2(i + 1) for i, rel in enumerate(ideal_ranking, start=1)
        )

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def _is_relevant(self, retrieved_path: str, relevant_paths: Set[str]) -> bool:
        """Check if retrieved path matches any relevant path.

        Uses fuzzy matching - checks if ground truth path is substring of retrieved.
        This handles cases where retrieved path has full repo path while ground truth
        has relative path.

        Args:
            retrieved_path: Retrieved file path
            relevant_paths: Set of relevant file paths from ground truth

        Returns:
            True if match found
        """
        for relevant_path in relevant_paths:
            # Normalize paths for comparison
            if relevant_path in retrieved_path or retrieved_path in relevant_path:
                return True
        return False

    def generate_report(self, results: Dict) -> str:
        """Generate markdown report from benchmark results.

        Args:
            results: Benchmark results dictionary

        Returns:
            Markdown formatted report
        """
        report = f"""# Embedding Model Benchmark Results

**Model**: {results['model']}
**Date**: {time.strftime('%Y-%m-%d')}
**Queries**: {len(self.queries)}

## Summary Metrics

| Metric | Value |
|--------|-------|
| Precision@5 | {results['precision_at_k'][5]:.3f} |
| Recall@10 | {results['recall_at_k'][10]:.3f} |
| MRR | {results['mrr']:.3f} |
| nDCG@5 | {results['ndcg_at_k'][5]:.3f} |
| Avg Latency | {results['avg_latency_ms']:.1f}ms |

## Precision@k

| k | Precision |
|---|-----------|
"""
        for k, precision in sorted(results["precision_at_k"].items()):
            report += f"| {k} | {precision:.3f} |\n"

        report += "\n## Recall@k\n\n| k | Recall |\n|---|--------|\n"
        for k, recall in sorted(results["recall_at_k"].items()):
            report += f"| {k} | {recall:.3f} |\n"

        report += "\n## By Category\n\n| Category | Precision@5 | Count |\n|----------|-------------|-------|\n"
        for category, data in sorted(results["by_category"].items()):
            report += (
                f"| {category} | {data['precision_at_5']:.3f} | {data['count']} |\n"
            )

        return report


# ============== Tests ==============


def test_benchmark_initialization():
    """Test that benchmark can load ground truth."""
    gt_path = Path(__file__).parent / "embedding_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = EmbeddingBenchmark(gt_path)
    assert len(benchmark.queries) > 0
    assert "metadata" in dir(benchmark)


def test_precision_calculation():
    """Test precision@k calculation."""
    gt_path = Path(__file__).parent / "embedding_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = EmbeddingBenchmark(gt_path)

    # Test perfect precision
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file1.sql", "file2.sql", "file3.sql"}
    assert benchmark._precision_at_k(retrieved, relevant) == 1.0

    # Test partial precision
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file1.sql", "file4.sql"}
    assert benchmark._precision_at_k(retrieved, relevant) == pytest.approx(1 / 3)

    # Test zero precision
    retrieved = ["file1.sql", "file2.sql"]
    relevant = {"file3.sql"}
    assert benchmark._precision_at_k(retrieved, relevant) == 0.0


def test_recall_calculation():
    """Test recall@k calculation."""
    gt_path = Path(__file__).parent / "embedding_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = EmbeddingBenchmark(gt_path)

    # Test perfect recall
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file1.sql", "file2.sql"}
    assert benchmark._recall_at_k(retrieved, relevant) == 1.0

    # Test partial recall
    retrieved = ["file1.sql", "file2.sql"]
    relevant = {"file1.sql", "file2.sql", "file3.sql"}
    assert benchmark._recall_at_k(retrieved, relevant) == pytest.approx(2 / 3)


def test_reciprocal_rank_calculation():
    """Test MRR calculation."""
    gt_path = Path(__file__).parent / "embedding_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = EmbeddingBenchmark(gt_path)

    # First result relevant
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file1.sql"}
    assert benchmark._reciprocal_rank(retrieved, relevant) == 1.0

    # Second result relevant
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file2.sql"}
    assert benchmark._reciprocal_rank(retrieved, relevant) == 0.5

    # Third result relevant
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file3.sql"}
    assert benchmark._reciprocal_rank(retrieved, relevant) == pytest.approx(1 / 3)

    # No relevant results
    retrieved = ["file1.sql", "file2.sql"]
    relevant = {"file4.sql"}
    assert benchmark._reciprocal_rank(retrieved, relevant) == 0.0


def test_ndcg_calculation():
    """Test nDCG@k calculation."""
    gt_path = Path(__file__).parent / "embedding_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = EmbeddingBenchmark(gt_path)

    # Perfect ranking
    retrieved = ["file1.sql", "file2.sql", "file3.sql"]
    relevant = {"file1.sql", "file2.sql"}
    ndcg = benchmark._ndcg_at_k(retrieved, relevant, k=3)
    assert ndcg == 1.0

    # Imperfect ranking
    retrieved = ["file3.sql", "file1.sql", "file2.sql"]
    relevant = {"file1.sql", "file2.sql"}
    ndcg = benchmark._ndcg_at_k(retrieved, relevant, k=3)
    assert 0.0 < ndcg < 1.0


def test_path_matching():
    """Test fuzzy path matching."""
    gt_path = Path(__file__).parent / "embedding_ground_truth.json"
    if not gt_path.exists():
        pytest.skip("Ground truth file not found")

    benchmark = EmbeddingBenchmark(gt_path)

    # Exact match
    assert benchmark._is_relevant("sql/schema/users.sql", {"sql/schema/users.sql"})

    # Substring match (ground truth is prefix)
    assert benchmark._is_relevant(
        "/repo/sql/schema/users.sql", {"sql/schema/users.sql"}
    )

    # Substring match (retrieved is prefix)
    assert benchmark._is_relevant("schema/users.sql", {"/full/path/schema/users.sql"})

    # No match
    assert not benchmark._is_relevant("sql/other.sql", {"sql/schema/users.sql"})
