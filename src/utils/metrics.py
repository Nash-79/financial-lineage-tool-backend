"""
Performance Metrics - Prometheus-compatible metrics collection.

This module provides lightweight metrics collection for monitoring ingestion pipeline
performance. Metrics can be exported to Prometheus or viewed directly via CLI.

Metrics Types:
- Counter: Monotonically increasing values (cache hits, files processed)
- Gauge: Values that can go up or down (active workers, queue size)
- Histogram: Distribution of values (batch sizes, processing duration)
"""

import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class CounterMetric:
    """Counter metric - monotonically increasing value."""

    name: str
    help: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: float = 1.0):
        """Increment counter by amount."""
        self.value += amount

    def get(self) -> float:
        """Get current value."""
        return self.value

    def reset(self):
        """Reset counter to zero."""
        self.value = 0.0


@dataclass
class GaugeMetric:
    """Gauge metric - value that can go up or down."""

    name: str
    help: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float):
        """Set gauge to specific value."""
        self.value = value

    def inc(self, amount: float = 1.0):
        """Increment gauge."""
        self.value += amount

    def dec(self, amount: float = 1.0):
        """Decrement gauge."""
        self.value -= amount

    def get(self) -> float:
        """Get current value."""
        return self.value


@dataclass
class HistogramMetric:
    """Histogram metric - distribution of values."""

    name: str
    help: str
    buckets: List[float] = field(
        default_factory=lambda: [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ]
    )
    labels: Dict[str, str] = field(default_factory=dict)

    # Internal tracking
    observations: List[float] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0
    bucket_counts: Dict[float, int] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize bucket counts."""
        for bucket in self.buckets:
            self.bucket_counts[bucket] = 0

    def observe(self, value: float):
        """Observe a value."""
        self.observations.append(value)
        self.sum += value
        self.count += 1

        # Update bucket counts
        for bucket in self.buckets:
            if value <= bucket:
                self.bucket_counts[bucket] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get histogram summary statistics."""
        if not self.observations:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_obs = sorted(self.observations)
        n = len(sorted_obs)

        return {
            "count": self.count,
            "sum": self.sum,
            "avg": self.sum / self.count if self.count > 0 else 0.0,
            "min": sorted_obs[0],
            "max": sorted_obs[-1],
            "p50": sorted_obs[int(n * 0.50)] if n > 0 else 0.0,
            "p95": sorted_obs[int(n * 0.95)] if n > 0 else 0.0,
            "p99": sorted_obs[int(n * 0.99)] if n > 0 else 0.0,
        }


class MetricsRegistry:
    """
    Central registry for all metrics.

    Thread-safe metrics collection with Prometheus-compatible export.
    """

    def __init__(self):
        """Initialize metrics registry."""
        self._lock = threading.Lock()
        self._counters: Dict[str, CounterMetric] = {}
        self._gauges: Dict[str, GaugeMetric] = {}
        self._histograms: Dict[str, HistogramMetric] = {}
        self._start_time = time.time()

    def counter(
        self, name: str, help: str, labels: Optional[Dict[str, str]] = None
    ) -> CounterMetric:
        """
        Get or create a counter metric.

        Args:
            name: Metric name
            help: Help text describing the metric
            labels: Optional labels for the metric

        Returns:
            CounterMetric instance
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._counters:
                self._counters[key] = CounterMetric(
                    name=name, help=help, labels=labels or {}
                )
            return self._counters[key]

    def gauge(
        self, name: str, help: str, labels: Optional[Dict[str, str]] = None
    ) -> GaugeMetric:
        """
        Get or create a gauge metric.

        Args:
            name: Metric name
            help: Help text describing the metric
            labels: Optional labels for the metric

        Returns:
            GaugeMetric instance
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(
                    name=name, help=help, labels=labels or {}
                )
            return self._gauges[key]

    def histogram(
        self,
        name: str,
        help: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> HistogramMetric:
        """
        Get or create a histogram metric.

        Args:
            name: Metric name
            help: Help text describing the metric
            buckets: Optional bucket boundaries
            labels: Optional labels for the metric

        Returns:
            HistogramMetric instance
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._histograms:
                hist = HistogramMetric(name=name, help=help, labels=labels or {})
                if buckets:
                    hist.buckets = buckets
                    hist.bucket_counts = {b: 0 for b in buckets}
                self._histograms[key] = hist
            return self._histograms[key]

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create unique key for metric with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def export_prometheus(self) -> str:
        """
        Export all metrics in Prometheus text format.

        Returns:
            String in Prometheus exposition format
        """
        lines = []

        with self._lock:
            # Export counters
            for counter in self._counters.values():
                lines.append(f"# HELP {counter.name} {counter.help}")
                lines.append(f"# TYPE {counter.name} counter")
                label_str = self._format_labels(counter.labels)
                lines.append(f"{counter.name}{label_str} {counter.value}")

            # Export gauges
            for gauge in self._gauges.values():
                lines.append(f"# HELP {gauge.name} {gauge.help}")
                lines.append(f"# TYPE {gauge.name} gauge")
                label_str = self._format_labels(gauge.labels)
                lines.append(f"{gauge.name}{label_str} {gauge.value}")

            # Export histograms
            for hist in self._histograms.values():
                lines.append(f"# HELP {hist.name} {hist.help}")
                lines.append(f"# TYPE {hist.name} histogram")
                label_str = self._format_labels(hist.labels)

                # Export buckets
                for bucket, count in sorted(hist.bucket_counts.items()):
                    bucket_label = self._format_labels(
                        {**hist.labels, "le": str(bucket)}
                    )
                    lines.append(f"{hist.name}_bucket{bucket_label} {count}")

                # Export +Inf bucket
                inf_label = self._format_labels({**hist.labels, "le": "+Inf"})
                lines.append(f"{hist.name}_bucket{inf_label} {hist.count}")

                # Export sum and count
                lines.append(f"{hist.name}_sum{label_str} {hist.sum}")
                lines.append(f"{hist.name}_count{label_str} {hist.count}")

        return "\n".join(lines) + "\n"

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus."""
        if not labels:
            return ""
        label_pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(label_pairs) + "}"

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all metrics.

        Returns:
            Dictionary with all metric values
        """
        with self._lock:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - self._start_time,
                "counters": {},
                "gauges": {},
                "histograms": {},
            }

            for key, counter in self._counters.items():
                summary["counters"][key] = counter.value

            for key, gauge in self._gauges.items():
                summary["gauges"][key] = gauge.value

            for key, hist in self._histograms.items():
                summary["histograms"][key] = hist.get_summary()

            return summary

    def reset(self):
        """Reset all metrics to initial state."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for gauge in self._gauges.values():
                gauge.set(0.0)
            for hist in self._histograms.values():
                hist.observations.clear()
                hist.sum = 0.0
                hist.count = 0
                for bucket in hist.buckets:
                    hist.bucket_counts[bucket] = 0


# Global registry instance
_global_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return _global_registry


# Convenience functions for accessing global registry
def counter(
    name: str, help: str, labels: Optional[Dict[str, str]] = None
) -> CounterMetric:
    """Get or create a counter from global registry."""
    return _global_registry.counter(name, help, labels)


def gauge(name: str, help: str, labels: Optional[Dict[str, str]] = None) -> GaugeMetric:
    """Get or create a gauge from global registry."""
    return _global_registry.gauge(name, help, labels)


def histogram(
    name: str,
    help: str,
    buckets: Optional[List[float]] = None,
    labels: Optional[Dict[str, str]] = None,
) -> HistogramMetric:
    """Get or create a histogram from global registry."""
    return _global_registry.histogram(name, help, buckets, labels)


# Ingestion Pipeline Metrics
# These are pre-defined metrics for the optimization pipeline

# Parse Cache Metrics
PARSE_CACHE_HIT_TOTAL = counter(
    "parse_cache_hit_total", "Total number of parse cache hits"
)

PARSE_CACHE_MISS_TOTAL = counter(
    "parse_cache_miss_total", "Total number of parse cache misses"
)

PARSE_CACHE_SIZE_BYTES = gauge(
    "parse_cache_size_bytes", "Current size of parse cache in bytes"
)

PARSE_CACHE_ENTRIES = gauge(
    "parse_cache_entries", "Current number of entries in parse cache"
)

# Batch Processing Metrics
BATCH_SIZE_HISTOGRAM = histogram(
    "batch_size_histogram",
    "Distribution of batch sizes",
    buckets=[1, 5, 10, 25, 50, 100, 200, 500],
)

BATCH_PROCESSING_DURATION_SECONDS = histogram(
    "batch_processing_duration_seconds", "Time taken to process a batch"
)

EVENTS_DEDUPLICATED_TOTAL = counter(
    "events_deduplicated_total", "Total number of deduplicated events"
)

# Worker Pool Metrics
FILES_PROCESSED_TOTAL = counter(
    "files_processed_total", "Total number of files processed"
)

FILES_FAILED_TOTAL = counter(
    "files_failed_total", "Total number of files that failed processing"
)

ACTIVE_WORKERS = gauge("active_workers", "Number of currently active workers")

QUEUE_SIZE = gauge("queue_size", "Current size of the task queue")

FILE_PROCESSING_DURATION_SECONDS = histogram(
    "file_processing_duration_seconds", "Time taken to process a single file"
)

# Neo4j Batch Metrics
NEO4J_BATCH_CREATE_TOTAL = counter(
    "neo4j_batch_create_total", "Total number of Neo4j batch operations"
)

NEO4J_ENTITIES_CREATED_TOTAL = counter(
    "neo4j_entities_created_total", "Total number of entities created in Neo4j"
)

NEO4J_RELATIONSHIPS_CREATED_TOTAL = counter(
    "neo4j_relationships_created_total",
    "Total number of relationships created in Neo4j",
)

NEO4J_BATCH_DURATION_SECONDS = histogram(
    "neo4j_batch_duration_seconds", "Time taken for Neo4j batch operations"
)

NEO4J_RETRY_TOTAL = counter(
    "neo4j_retry_total", "Total number of Neo4j operation retries"
)


def print_metrics_summary():
    """Print a human-readable summary of all metrics."""
    summary = get_registry().get_summary()

    print("=" * 70)
    print("METRICS SUMMARY")
    print("=" * 70)
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Uptime: {summary['uptime_seconds']:.2f}s")
    print()

    if summary["counters"]:
        print("Counters:")
        for name, value in summary["counters"].items():
            print(f"  {name}: {value}")
        print()

    if summary["gauges"]:
        print("Gauges:")
        for name, value in summary["gauges"].items():
            print(f"  {name}: {value}")
        print()

    if summary["histograms"]:
        print("Histograms:")
        for name, stats in summary["histograms"].items():
            print(f"  {name}:")
            print(f"    Count: {stats['count']}")
            print(f"    Sum: {stats['sum']:.2f}")
            print(f"    Avg: {stats['avg']:.2f}")
            if stats["count"] > 0:
                print(f"    Min: {stats['min']:.2f}")
                print(f"    Max: {stats['max']:.2f}")
                print(f"    P50: {stats['p50']:.2f}")
                print(f"    P95: {stats['p95']:.2f}")
                print(f"    P99: {stats['p99']:.2f}")
        print()

    print("=" * 70)


if __name__ == "__main__":
    # Example usage
    print("Metrics Module - Example Usage")
    print()

    # Simulate some metrics
    PARSE_CACHE_HIT_TOTAL.inc(150)
    PARSE_CACHE_MISS_TOTAL.inc(50)
    PARSE_CACHE_ENTRIES.set(1250)

    for i in range(10):
        BATCH_SIZE_HISTOGRAM.observe(25 + i * 5)
        BATCH_PROCESSING_DURATION_SECONDS.observe(0.5 + i * 0.1)

    FILES_PROCESSED_TOTAL.inc(100)
    FILES_FAILED_TOTAL.inc(5)
    ACTIVE_WORKERS.set(4)
    QUEUE_SIZE.set(15)

    # Print summary
    print_metrics_summary()

    # Print Prometheus format
    print("\nPrometheus Format:")
    print("=" * 70)
    print(get_registry().export_prometheus())
