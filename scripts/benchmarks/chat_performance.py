#!/usr/bin/env python3
"""
Chat API Performance Benchmark Script

Measures P50/P95/P99 latency for chat endpoints and compares
performance with/without optimizations (caching, skip_memory, etc.)

Usage:
    python scripts/benchmarks/chat_performance.py [--iterations 10] [--base-url http://localhost:8000]
"""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    endpoint: str
    iterations: int
    latencies_ms: List[float]
    errors: int

    @property
    def p50(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.50)
        return sorted_latencies[idx]

    @property
    def p95(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p99(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def mean(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    @property
    def std_dev(self) -> float:
        if len(self.latencies_ms) < 2:
            return 0.0
        return statistics.stdev(self.latencies_ms)


class ChatBenchmark:
    """Benchmark runner for chat API endpoints."""

    TEST_QUERIES = [
        "What tables are used in the customer pipeline?",
        "Show me the lineage of the sales table",
        "Where does the revenue column come from?",
        "What are the upstream sources for fact_orders?",
        "Explain the data flow for customer analytics",
    ]

    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self.client.aclose()

    async def _make_request(
        self,
        endpoint: str,
        query: str,
        session_id: Optional[str] = None,
        skip_memory: bool = False,
    ) -> tuple[float, bool]:
        """Make a single request and return (latency_ms, success)."""
        payload = {"query": query}
        if session_id:
            payload["session_id"] = session_id
        if skip_memory:
            payload["skip_memory"] = True

        start = time.perf_counter()
        try:
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                json=payload,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            return elapsed_ms, response.status_code == 200
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"  [!] Request failed: {e}")
            return elapsed_ms, False

    async def benchmark_endpoint(
        self,
        endpoint: str,
        iterations: int,
        session_id: Optional[str] = None,
        skip_memory: bool = False,
        warmup: int = 2,
    ) -> BenchmarkResult:
        """Run benchmark for a specific endpoint."""
        print(f"\nBenchmarking {endpoint} ({iterations} iterations)...")

        # Warmup runs (not counted)
        for i in range(warmup):
            query = self.TEST_QUERIES[i % len(self.TEST_QUERIES)]
            await self._make_request(endpoint, query, session_id, skip_memory)
            print(f"  Warmup {i+1}/{warmup}")

        # Actual benchmark runs
        latencies = []
        errors = 0

        for i in range(iterations):
            query = self.TEST_QUERIES[i % len(self.TEST_QUERIES)]
            latency_ms, success = await self._make_request(
                endpoint, query, session_id, skip_memory
            )

            if success:
                latencies.append(latency_ms)
                print(f"  Iteration {i+1}/{iterations}: {latency_ms:.1f}ms")
            else:
                errors += 1
                print(f"  Iteration {i+1}/{iterations}: ERROR")

        return BenchmarkResult(
            endpoint=endpoint,
            iterations=iterations,
            latencies_ms=latencies,
            errors=errors,
        )

    async def run_full_benchmark(self, iterations: int = 10) -> dict:
        """Run complete benchmark suite."""
        results = {}

        # 1. Baseline: /api/chat/deep without optimizations
        print("\n" + "="*60)
        print("1. BASELINE: /api/chat/deep (cold, no session)")
        print("="*60)
        results["deep_cold"] = await self.benchmark_endpoint(
            "/api/chat/deep",
            iterations=iterations,
        )

        # 2. With session (memory context)
        print("\n" + "="*60)
        print("2. WITH MEMORY: /api/chat/deep (with session_id)")
        print("="*60)
        results["deep_with_memory"] = await self.benchmark_endpoint(
            "/api/chat/deep",
            iterations=iterations,
            session_id="benchmark-session-001",
        )

        # 3. With skip_memory flag
        print("\n" + "="*60)
        print("3. SKIP MEMORY: /api/chat/deep (skip_memory=true)")
        print("="*60)
        results["deep_skip_memory"] = await self.benchmark_endpoint(
            "/api/chat/deep",
            iterations=iterations,
            session_id="benchmark-session-001",
            skip_memory=True,
        )

        # 4. Repeated queries (cache hits)
        print("\n" + "="*60)
        print("4. CACHE HITS: /api/chat/deep (same query repeated)")
        print("="*60)
        # Use same query to test embedding cache
        single_query = self.TEST_QUERIES[0]
        cache_latencies = []
        for i in range(iterations):
            latency_ms, success = await self._make_request(
                "/api/chat/deep", single_query, skip_memory=True
            )
            if success:
                cache_latencies.append(latency_ms)
                print(f"  Iteration {i+1}/{iterations}: {latency_ms:.1f}ms")

        results["deep_cached"] = BenchmarkResult(
            endpoint="/api/chat/deep (cached)",
            iterations=iterations,
            latencies_ms=cache_latencies,
            errors=iterations - len(cache_latencies),
        )

        # 5. Simple text endpoint (baseline LLM latency)
        print("\n" + "="*60)
        print("5. LLM BASELINE: /api/chat/text (no RAG)")
        print("="*60)
        results["text_baseline"] = await self.benchmark_endpoint(
            "/api/chat/text",
            iterations=iterations,
        )

        return results

    def print_summary(self, results: dict):
        """Print benchmark summary table."""
        print("\n" + "="*80)
        print("BENCHMARK SUMMARY")
        print("="*80)
        print(f"{'Endpoint':<35} {'P50':>10} {'P95':>10} {'P99':>10} {'Mean':>10} {'Errors':>8}")
        print("-"*80)

        for name, result in results.items():
            print(
                f"{result.endpoint:<35} "
                f"{result.p50:>9.1f}ms "
                f"{result.p95:>9.1f}ms "
                f"{result.p99:>9.1f}ms "
                f"{result.mean:>9.1f}ms "
                f"{result.errors:>8}"
            )

        print("-"*80)

        # Calculate improvements
        if "deep_cold" in results and "deep_skip_memory" in results:
            cold = results["deep_cold"].mean
            skip = results["deep_skip_memory"].mean
            if cold > 0:
                improvement = ((cold - skip) / cold) * 100
                print(f"\nMemory skip improvement: {improvement:.1f}% faster")

        if "deep_cold" in results and "deep_cached" in results:
            cold = results["deep_cold"].mean
            cached = results["deep_cached"].mean
            if cold > 0:
                improvement = ((cold - cached) / cold) * 100
                print(f"Cache hit improvement: {improvement:.1f}% faster")


async def main():
    parser = argparse.ArgumentParser(description="Chat API Performance Benchmark")
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=10,
        help="Number of iterations per benchmark (default: 10)"
    )
    parser.add_argument(
        "--base-url", "-u",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file for results"
    )

    args = parser.parse_args()

    print(f"Chat API Performance Benchmark")
    print(f"Base URL: {args.base_url}")
    print(f"Iterations: {args.iterations}")

    benchmark = ChatBenchmark(args.base_url)

    try:
        results = await benchmark.run_full_benchmark(args.iterations)
        benchmark.print_summary(results)

        # Export to JSON if requested
        if args.output:
            export_data = {
                name: {
                    "endpoint": r.endpoint,
                    "iterations": r.iterations,
                    "p50_ms": r.p50,
                    "p95_ms": r.p95,
                    "p99_ms": r.p99,
                    "mean_ms": r.mean,
                    "std_dev_ms": r.std_dev,
                    "errors": r.errors,
                    "latencies_ms": r.latencies_ms,
                }
                for name, r in results.items()
            }
            with open(args.output, "w") as f:
                json.dump(export_data, f, indent=2)
            print(f"\nResults exported to {args.output}")

    finally:
        await benchmark.close()


if __name__ == "__main__":
    asyncio.run(main())
