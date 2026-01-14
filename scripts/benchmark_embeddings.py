#!/usr/bin/env python
"""
Benchmark embedding models for SQL lineage retrieval quality.

Usage:
    python scripts/benchmark_embeddings.py --model nomic-embed-text
    python scripts/benchmark_embeddings.py --compare-all
    python scripts/benchmark_embeddings.py --report-only

Examples:
    # Test single model
    python scripts/benchmark_embeddings.py --model nomic-embed-text

    # Compare all available models
    python scripts/benchmark_embeddings.py --compare-all

    # Generate report from cached results
    python scripts/benchmark_embeddings.py --report-only
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.benchmarks.test_embedding_quality import EmbeddingBenchmark


# Ollama models to benchmark (all free, no API costs)
OLLAMA_MODELS = [
    {
        "name": "nomic-embed-text",
        "dimensions": 768,
        "description": "Current production model",
    },
    {"name": "all-minilm-l6-v2", "dimensions": 384, "description": "Lightweight, fast"},
    {
        "name": "bge-small-en-v1.5",
        "dimensions": 384,
        "description": "BGE family, high quality",
    },
]


def mock_search(query: str, limit: int, model: str = "nomic-embed-text"):
    """Mock search function for demonstration.

    In production, this would call:
        await llamaindex_service.query(query, limit=limit)

    Returns mock results with file_path payload.
    """
    # TODO: Replace with actual LlamaIndex search when ready
    print(f"[Mock] Searching '{query}' with {model} (limit={limit})")
    return [
        {"payload": {"file_path": f"sql/mock_result_{i}.sql"}} for i in range(limit)
    ]


def run_single_benchmark(model_name: str, save_results: bool = True):
    """Run benchmark for a single embedding model.

    Args:
        model_name: Name of the Ollama model to test
        save_results: Whether to save results to JSON file

    Returns:
        Benchmark results dictionary
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking: {model_name}")
    print(f"{'='*60}\n")

    # Load benchmark
    gt_path = (
        Path(__file__).parent.parent
        / "tests"
        / "benchmarks"
        / "embedding_ground_truth.json"
    )
    benchmark = EmbeddingBenchmark(gt_path)

    # Create search function with model
    def search_fn(query, limit):
        return mock_search(query, limit, model=model_name)

    # Run benchmark
    results = benchmark.run_benchmark(
        search_function=search_fn, k_values=[1, 3, 5, 10], embedding_model=model_name
    )

    # Print summary
    print(f"\n[Results Summary]:")
    print(f"  Precision@5:  {results['precision_at_k'][5]:.3f}")
    print(f"  Recall@10:    {results['recall_at_k'][10]:.3f}")
    print(f"  MRR:          {results['mrr']:.3f}")
    print(f"  nDCG@5:       {results['ndcg_at_k'][5]:.3f}")
    print(f"  Avg Latency:  {results['avg_latency_ms']:.1f}ms")

    # Save results
    if save_results:
        results_dir = Path(__file__).parent.parent / "docs" / "benchmarks"
        results_dir.mkdir(parents=True, exist_ok=True)

        results_file = results_dir / f"{model_name.replace(':', '_')}_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n[Saved] Results saved to: {results_file}")

    return results


def compare_all_models():
    """Run benchmarks for all Ollama models and generate comparison report."""
    print("\n" + "=" * 60)
    print("EMBEDDING MODEL COMPARISON")
    print("=" * 60)

    all_results = {}

    for model_info in OLLAMA_MODELS:
        model_name = model_info["name"]
        results = run_single_benchmark(model_name, save_results=True)
        all_results[model_name] = {
            **results,
            "dimensions": model_info["dimensions"],
            "description": model_info["description"],
        }

    # Generate comparison report
    generate_comparison_report(all_results)


def generate_comparison_report(all_results: dict):
    """Generate markdown comparison report.

    Args:
        all_results: Dictionary mapping model names to results
    """
    report_dir = Path(__file__).parent.parent / "docs" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = (
        report_dir / f"embedding_comparison_{datetime.now().strftime('%Y%m%d')}.md"
    )

    gt_path = (
        Path(__file__).parent.parent
        / "tests"
        / "benchmarks"
        / "embedding_ground_truth.json"
    )
    benchmark = EmbeddingBenchmark(gt_path)

    report = benchmark.generate_report(next(iter(all_results.values())))

    # Enhanced comparison table
    report = f"""# Embedding Model Comparison

**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Dataset**: {len(benchmark.queries)} SQL lineage queries
**Metrics**: Precision@k, Recall@k, MRR, nDCG@k

---

## Summary

| Model | Dims | P@5 | R@10 | MRR | nDCG@5 | Latency |
|-------|------|-----|------|-----|--------|---------|
"""

    for model_name, results in all_results.items():
        dims = results.get("dimensions", "?")
        p5 = results["precision_at_k"][5]
        r10 = results["recall_at_k"][10]
        mrr = results["mrr"]
        ndcg5 = results["ndcg_at_k"][5]
        lat = results["avg_latency_ms"]

        report += f"| {model_name} | {dims} | {p5:.3f} | {r10:.3f} | {mrr:.3f} | {ndcg5:.3f} | {lat:.1f}ms |\n"

    report += "\n---\n\n"

    # Find best model
    best_model = max(all_results.items(), key=lambda x: x[1]["precision_at_k"][5])
    report += f"""## 🏆 Recommendation

**Best Model**: `{best_model[0]}`

**Why?**
- Highest Precision@5: {best_model[1]["precision_at_k"][5]:.3f}
- Recall@10: {best_model[1]["recall_at_k"][10]:.3f}
- Avg Latency: {best_model[1]["avg_latency_ms"]:.1f}ms

**Next Steps**:
1. Update `EMBEDDING_MODEL` in config.py to `{best_model[0]}`
2. Pull model: `ollama pull {best_model[0]}`
3. Reindex vector database with new embeddings
4. Monitor query quality in production

---

## Detailed Results

"""

    # Add individual model sections
    for model_name, results in all_results.items():
        report += f"\n### {model_name}\n\n"
        report += f"**Description**: {results.get('description', 'N/A')}\n\n"
        report += "#### Precision by k\n\n| k | Precision |\n|---|-----------|"
        for k, precision in sorted(results["precision_at_k"].items()):
            report += f"\n| {k} | {precision:.3f} |"

        report += "\n\n#### By Category\n\n| Category | Precision@5 | Queries |\n|----------|-------------|---------|"
        for category, data in sorted(results["by_category"].items()):
            report += (
                f"\n| {category} | {data['precision_at_5']:.3f} | {data['count']} |"
            )

        report += "\n\n---\n"

    # Write report
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n[Report] Comparison report saved to: {report_path}")
    print(f"\n[DONE] Benchmarking complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark embedding models for SQL lineage retrieval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--model", help="Single model to benchmark (e.g., 'nomic-embed-text')"
    )
    parser.add_argument(
        "--compare-all", action="store_true", help="Compare all available Ollama models"
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate report from existing result files",
    )
    parser.add_argument(
        "--list-models", action="store_true", help="List available models"
    )

    args = parser.parse_args()

    if args.list_models:
        print("\nAvailable Embedding Models:\n")
        for model in OLLAMA_MODELS:
            print(f"  • {model['name']} ({model['dimensions']}-dim)")
            print(f"    {model['description']}\n")
        return

    if args.compare_all:
        compare_all_models()
    elif args.model:
        run_single_benchmark(args.model)
    elif args.report_only:
        # Load cached results and generate report
        results_dir = Path(__file__).parent.parent / "docs" / "benchmarks"
        all_results = {}

        for model_info in OLLAMA_MODELS:
            model_name = model_info["name"]
            results_file = results_dir / f"{model_name.replace(':', '_')}_results.json"

            if results_file.exists():
                with open(results_file) as f:
                    results = json.load(f)
                all_results[model_name] = {
                    **results,
                    "dimensions": model_info["dimensions"],
                    "description": model_info["description"],
                }

        if all_results:
            generate_comparison_report(all_results)
        else:
            print("❌ No cached results found. Run benchmarks first with --compare-all")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
