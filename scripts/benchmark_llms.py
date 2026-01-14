#!/usr/bin/env python
"""
Benchmark LLM models for SQL lineage question answering quality.

Tests multiple models (Ollama, OpenRouter) against ground truth Q&A
dataset to measure accuracy, citation quality, hallucination rate, and latency.

Usage:
    python scripts/benchmark_llms.py --model llama3.1:8b
    python scripts/benchmark_llms.py --provider ollama
    python scripts/benchmark_llms.py --compare-all
    python scripts/benchmark_llms.py --list-models

Examples:
    # Test single model
    python scripts/benchmark_llms.py --model llama3.1:8b

    # Compare all Ollama models
    python scripts/benchmark_llms.py --provider ollama

    # Compare all free models
    python scripts/benchmark_llms.py --compare-all
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.benchmarks.test_llm_quality import LLMBenchmark


# Model configurations
MODELS = {
    "ollama": [
        {"name": "llama3.1:8b", "description": "Llama 3.1 8B (full precision)"},
        {
            "name": "llama3.1:8b-q4",
            "description": "Llama 3.1 8B (4-bit quantized, faster)",
        },
    ],
    "openrouter": [
        {
            "name": "meta-llama/llama-3.1-8b-instruct:free",
            "description": "Llama 3.1 8B (free tier)",
        },
        {
            "name": "google/gemma-2-9b-it:free",
            "description": "Gemma 2 9B (Google, free)",
        },
    ],
}


import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing config
load_dotenv(override=True)

from src.llm.remote_clients import OpenRouterClient
from src.services.ollama_service import OllamaClient
from src.api.config import config


# Global client instances
OPENROUTER_CLIENT = None
OLLAMA_CLIENT = None


def init_llm_clients():
    """Initialize LLM clients based on available API keys."""
    global OPENROUTER_CLIENT, OLLAMA_CLIENT

    # Refresh config to pick up any new env vars
    if config.OPENROUTER_API_KEY:
        OPENROUTER_CLIENT = OpenRouterClient(config.OPENROUTER_API_KEY)
        print(f"✓ OpenRouter client initialized")

    # Initialize Ollama with local host
    OLLAMA_CLIENT = OllamaClient(host=config.OLLAMA_HOST)
    print(f"✓ Ollama client initialized ({config.OLLAMA_HOST})")


async def real_llm_function(
    question: str, context: List[Dict], model_name: str, provider: str
) -> str:
    """Real LLM function using actual API clients.

    Args:
        question: User question
        context: List of retrieved code chunks
        model_name: Model to use
        provider: Provider (ollama, openrouter)

    Returns:
        Generated answer from LLM
    """
    # Build context string from retrieved chunks
    context_str = "\n\n".join(
        [
            f"File: {chunk.get('payload', {}).get('file_path', 'unknown')}\n{chunk.get('payload', {}).get('content', '')}"
            for chunk in context[:5]  # Limit to top 5 chunks
        ]
    )

    # Build prompt
    prompt = f"""You are a SQL lineage expert. Answer the question based on the provided code context.

Context:
{context_str}

Question: {question}

Instructions:
- Provide accurate, specific answers
- Cite file paths when referencing code
- List all relevant entities (tables, columns, etc.)
- Do not hallucinate information not in the context
- If unsure, say "Based on the provided context, I cannot determine..."

Answer:"""

    # Call appropriate LLM provider
    try:
        if provider == "openrouter":
            if not OPENROUTER_CLIENT:
                raise ValueError("OPENROUTER_API_KEY not configured")
            return await OPENROUTER_CLIENT.generate(
                prompt, model=model_name, temperature=0.3
            )

        elif provider == "ollama":
            if not OLLAMA_CLIENT:
                raise ValueError("Ollama not available")
            return await OLLAMA_CLIENT.generate(
                prompt, model=model_name, temperature=0.3
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")

    except Exception as e:
        raise RuntimeError(f"LLM generation failed ({provider}:{model_name}): {e}")


def real_search_function(query: str, limit: int) -> List[Dict]:
    """Retrieve context from Qdrant using vector search."""
    # Initialize search clients if not already done
    global OLLAMA_CLIENT
    if not OLLAMA_CLIENT:
        OLLAMA_CLIENT = OllamaClient(host=config.OLLAMA_HOST)

    try:
        # Generate embedding for query
        # We need an event loop for async call
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        embedding = loop.run_until_complete(
            OLLAMA_CLIENT.embed(query, model=config.EMBEDDING_MODEL)
        )

        # Search Qdrant
        from src.services.qdrant_service import QdrantLocalClient

        qdrant = QdrantLocalClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

        search_results = loop.run_until_complete(
            qdrant.search(
                collection=config.QDRANT_COLLECTION, vector=embedding, limit=limit
            )
        )

        # Format results for LLM
        context = []
        for res in search_results:
            # Handle both dict (from wrapper) and object (from official client) results
            if hasattr(res, "payload"):
                payload = res.payload
                score = res.score
            else:
                payload = res.get("payload", {})
                score = res.get("score", 0.0)

            context.append(
                {
                    "payload": {
                        "file_path": payload.get("file_path", "unknown"),
                        "content": payload.get("content", ""),
                        "score": score,
                    }
                }
            )

        print(f"      [Search] Found {len(context)} chunks for query: {query[:30]}...")
        return context

    except Exception as e:
        print(f"      [Search Error] {e}")
        return []


def run_single_benchmark(model_name: str, provider: str, save_results: bool = True):
    """Run benchmark for a single LLM model.

    Args:
        model_name: Name of model to test
        provider: Provider (ollama, openrouter)
        save_results: Whether to save results to JSON

    Returns:
        Benchmark results dictionary
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking: {model_name} ({provider})")
    print(f"{'='*60}\n")

    # Initialize LLM clients
    init_llm_clients()

    # Load benchmark
    gt_path = (
        Path(__file__).parent.parent / "tests" / "benchmarks" / "llm_ground_truth.json"
    )
    benchmark = LLMBenchmark(gt_path)

    # Create wrapper for async LLM function
    def llm_wrapper(question: str, context: List[Dict]) -> str:
        """Synchronous wrapper for async LLM function."""
        return asyncio.run(real_llm_function(question, context, model_name, provider))

    # Run benchmark with real LLM client
    print(f"[Status] Running {len(benchmark.qa_pairs)} test queries...")
    results = benchmark.run_benchmark(
        llm_function=llm_wrapper,
        search_function=real_search_function,
        model_name=model_name,
        provider=provider,
    )

    # Print summary
    print(f"\n[Results Summary]")
    print(f"  Accuracy:         {results['accuracy']:.3f} (target: > 0.80)")
    print(f"  Citation Quality: {results['citation_quality']:.3f} (target: > 0.90)")
    print(f"  Hallucination:    {results['hallucination_rate']:.3f} (target: < 0.10)")
    print(f"  Completeness:     {results['completeness']:.3f} (target: > 0.90)")
    print(
        f"  Avg Latency:      {results.get('avg_latency_ms', 0):.0f}ms (target: < 3000ms)"
    )

    # Calculate grade
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

    print(f"\n  Overall Grade:    {grade} ({grade_score:.3f})")

    # Save results
    if save_results:
        results_dir = (
            Path(__file__).parent.parent / "docs" / "benchmarks" / "llm_results"
        )
        results_dir.mkdir(parents=True, exist_ok=True)

        safe_name = model_name.replace(":", "_").replace("/", "_")
        results_file = results_dir / f"{provider}_{safe_name}_results.json"

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n[Saved] Results saved to: {results_file}")

    return results


def compare_provider(provider: str):
    """Run benchmarks for all models from a provider.

    Args:
        provider: Provider name (ollama, openrouter)
    """
    if provider not in MODELS:
        print(f"❌ Unknown provider: {provider}")
        print(f"Available providers: {', '.join(MODELS.keys())}")
        return

    print(f"\n{'='*60}")
    print(f"COMPARING {provider.upper()} MODELS")
    print(f"{'='*60}")

    all_results = {}
    for model_info in MODELS[provider]:
        results = run_single_benchmark(model_info["name"], provider, save_results=True)
        all_results[model_info["name"]] = {
            **results,
            "description": model_info["description"],
        }

    # Generate provider comparison report
    generate_provider_report(all_results, provider)


def compare_all_models():
    """Run benchmarks for all available models and generate comparison report."""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE LLM COMPARISON")
    print("Testing all free models across providers")
    print("=" * 60)

    all_results = {}

    for provider, models in MODELS.items():
        for model_info in models:
            model_name = model_info["name"]
            results = run_single_benchmark(model_name, provider, save_results=True)
            all_results[f"{provider}:{model_name}"] = {
                **results,
                "description": model_info["description"],
            }

    # Generate comprehensive comparison report
    generate_comprehensive_report(all_results)


def generate_provider_report(all_results: dict, provider: str):
    """Generate markdown comparison report for a single provider.

    Args:
        all_results: Dictionary mapping model names to results
        provider: Provider name
    """
    report_dir = Path(__file__).parent.parent / "docs" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = (
        report_dir / f"{provider}_comparison_{datetime.now().strftime('%Y%m%d')}.md"
    )

    report = f"""# {provider.capitalize()} LLM Quality Comparison

**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Provider**: {provider}
**Models Tested**: {len(all_results)}
**Dataset**: 20 SQL lineage Q&A pairs

---

## Summary

| Model | Accuracy | Citation | Halluc. | Complete | Latency | Grade |
|-------|----------|----------|---------|----------|---------|-------|
"""

    for model_name, results in all_results.items():
        acc = results["accuracy"]
        cit = results["citation_quality"]
        hal = results["hallucination_rate"]
        comp = results["completeness"]
        lat = results.get("avg_latency_ms", 0)

        grade_score = acc * 0.35 + cit * 0.20 + (1 - hal) * 0.25 + comp * 0.20
        if grade_score >= 0.9:
            grade = "A"
        elif grade_score >= 0.8:
            grade = "B"
        elif grade_score >= 0.7:
            grade = "C"
        else:
            grade = "D"

        report += f"| {model_name} | {acc:.3f} | {cit:.3f} | {hal:.3f} | {comp:.3f} | {lat:.0f}ms | {grade} |\n"

    # Find best model
    best_model = max(all_results.items(), key=lambda x: x[1]["accuracy"])

    report += f"""

---

## [WINNER] Recommendation

**Best {provider.capitalize()} Model**: `{best_model[0]}`

**Why?**
- Accuracy: {best_model[1]["accuracy"]:.3f}
- Citation Quality: {best_model[1]["citation_quality"]:.3f}
- Hallucination Rate: {best_model[1]["hallucination_rate"]:.3f}
- Completeness: {best_model[1]["completeness"]:.3f}

**Description**: {best_model[1].get("description", "N/A")}

---

## Detailed Results by Category

"""

    for model_name, results in all_results.items():
        report += f"\n### {model_name}\n\n"
        report += "| Category | Accuracy | Completeness |\n|----------|----------|--------------|"
        for category, data in sorted(results.get("by_category", {}).items()):
            report += f"\n| {category} | {data['accuracy']:.3f} | {data['completeness']:.3f} |"
        report += "\n"

    # Write report
    with open(report_path, "w") as f:
        f.write(report)

    print(
        f"\n[Report] {provider.capitalize()} comparison report saved to: {report_path}"
    )


def generate_comprehensive_report(all_results: dict):
    """Generate comprehensive comparison report across all providers.

    Args:
        all_results: Dictionary mapping "provider:model" to results
    """
    report_dir = Path(__file__).parent.parent / "docs" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = (
        report_dir / f"llm_comprehensive_{datetime.now().strftime('%Y%m%d')}.md"
    )

    report = f"""# Comprehensive LLM Quality Benchmark

**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Models Tested**: {len(all_results)}
**Dataset**: 20 SQL lineage Q&A pairs
**Providers**: Ollama, OpenRouter

---

## Executive Summary

| Provider:Model | Accuracy | Citation | Halluc. | Complete | Latency | Grade |
|----------------|----------|----------|---------|----------|---------|-------|
"""

    # Sort by accuracy descending
    sorted_results = sorted(
        all_results.items(), key=lambda x: x[1]["accuracy"], reverse=True
    )

    for key, results in sorted_results:
        acc = results["accuracy"]
        cit = results["citation_quality"]
        hal = results["hallucination_rate"]
        comp = results["completeness"]
        lat = results.get("avg_latency_ms", 0)

        grade_score = acc * 0.35 + cit * 0.20 + (1 - hal) * 0.25 + comp * 0.20
        if grade_score >= 0.9:
            grade = "A ✨"
        elif grade_score >= 0.8:
            grade = "B ✅"
        elif grade_score >= 0.7:
            grade = "C ⚠️"
        else:
            grade = "D ❌"

        report += f"| {key} | {acc:.3f} | {cit:.3f} | {hal:.3f} | {comp:.3f} | {lat:.0f}ms | {grade} |\n"

    # Overall recommendation
    best_key, best_results = sorted_results[0]

    report += f"""

---

## 🏆 Overall Recommendation

**Winner**: `{best_key}`

**Strengths**:
- Highest accuracy: {best_results["accuracy"]:.3f}
- Citation quality: {best_results["citation_quality"]:.3f}
- Hallucination rate: {best_results["hallucination_rate"]:.3f}
- Completeness: {best_results["completeness"]:.3f}

**Description**: {best_results.get("description", "N/A")}

---

## Production Deployment Strategy

**Recommended Fallback Chain**:

1. **Primary**: {best_key} (best quality)
2. **Fallback**: ollama:llama3.1:8b (privacy, local)

**Rationale**:
- Primary provides best accuracy for most queries
- Fallback ensures privacy-sensitive queries stay local

---

## Trade-offs Analysis

### Cloud vs Local

**Cloud Models (OpenRouter)**:
- ✅ Higher accuracy
- ✅ Lower latency
- ❌ Data sent externally
- ❌ Rate limits
- ❌ Requires internet

**Local Models (Ollama)**:
- ✅ Complete privacy
- ✅ No rate limits
- ✅ Works offline
- ❌ Lower accuracy
- ❌ Higher latency
- ❌ Requires GPU

---

## Next Steps

1. **Deploy winner model** as primary in config
2. **Set up fallback chain** in InferenceRouter
3. **Monitor quality metrics** in production
4. **A/B test** with real user queries
5. **Fine-tune** prompts based on failures

"""

    # Write report
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n[Report] Comprehensive comparison report saved to: {report_path}")
    print(f"\n[DONE] Benchmarking complete!")


def list_models():
    """List all available models for benchmarking."""
    print("\n📋 Available LLM Models:\n")

    for provider, models in MODELS.items():
        print(f"**{provider.upper()}**:")
        for model in models:
            print(f"  • {model['name']}")
            print(f"    {model['description']}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark LLM models for SQL lineage Q&A quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--model", help="Single model to benchmark (e.g., 'llama3.1:8b')"
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "openrouter"],
        help="Test all models from a provider",
    )
    parser.add_argument(
        "--compare-all",
        action="store_true",
        help="Compare all available models across providers",
    )
    parser.add_argument(
        "--list-models", action="store_true", help="List available models"
    )

    args = parser.parse_args()

    if args.list_models:
        list_models()
    elif args.compare_all:
        compare_all_models()
    elif args.provider:
        compare_provider(args.provider)
    elif args.model:
        # Detect provider from model name
        provider = "ollama"  # default
        for prov, models in MODELS.items():
            if any(m["name"] == args.model for m in models):
                provider = prov
                break

        run_single_benchmark(args.model, provider)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
