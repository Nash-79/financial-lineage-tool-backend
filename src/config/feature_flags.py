"""
Feature Flags - Runtime configuration for ingestion pipeline optimizations.

This module provides feature flags for safe gradual rollout and quick rollback
of optimization features in production environments.
"""

import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


class FeatureFlags:
    """
    Feature flags for ingestion pipeline optimizations.

    Each flag can be controlled via environment variables, allowing:
    - Gradual rollout (enable features one at a time)
    - A/B testing (enable for subset of workloads)
    - Quick rollback (disable via env var without code changes)
    - Emergency fallback to baseline behavior

    Environment Variables:
        FEATURE_PARSE_CACHE: Enable parse result caching (default: true)
        FEATURE_BATCHING: Enable event batching and debouncing (default: true)
        FEATURE_NEO4J_BATCH: Enable Neo4j batch operations (default: true)
        FEATURE_PARALLEL: Enable parallel worker pool (default: true)
        FEATURE_METRICS: Enable Prometheus metrics collection (default: true)
    """

    # Parse caching feature
    ENABLE_PARSE_CACHE = os.getenv("FEATURE_PARSE_CACHE", "true").lower() == "true"

    # Batch processing feature
    ENABLE_BATCHING = os.getenv("FEATURE_BATCHING", "true").lower() == "true"

    # Neo4j batch operations feature
    ENABLE_NEO4J_BATCHING = os.getenv("FEATURE_NEO4J_BATCH", "true").lower() == "true"

    # Parallel worker pool feature
    ENABLE_PARALLEL_WORKERS = os.getenv("FEATURE_PARALLEL", "true").lower() == "true"

    # Metrics collection feature
    ENABLE_METRICS = os.getenv("FEATURE_METRICS", "true").lower() == "true"

    @classmethod
    def get_status(cls) -> Dict[str, bool]:
        """
        Get current status of all feature flags.

        Returns:
            Dictionary mapping feature names to their enabled status
        """
        return {
            "parse_cache": cls.ENABLE_PARSE_CACHE,
            "batching": cls.ENABLE_BATCHING,
            "neo4j_batching": cls.ENABLE_NEO4J_BATCHING,
            "parallel_workers": cls.ENABLE_PARALLEL_WORKERS,
            "metrics": cls.ENABLE_METRICS,
        }

    @classmethod
    def disable_all_optimizations(cls):
        """
        Emergency fallback: Disable all optimizations.

        Use this to quickly revert to baseline behavior in case of issues.
        This is a runtime override that doesn't require code changes.

        Example:
            >>> FeatureFlags.disable_all_optimizations()
            >>> # Now running in baseline mode
        """
        cls.ENABLE_PARSE_CACHE = False
        cls.ENABLE_BATCHING = False
        cls.ENABLE_NEO4J_BATCHING = False
        cls.ENABLE_PARALLEL_WORKERS = False
        cls.ENABLE_METRICS = False

        logger.warning(
            "🚨 ALL OPTIMIZATIONS DISABLED - Running in baseline mode. "
            "This will result in significantly reduced performance."
        )

    @classmethod
    def enable_all_optimizations(cls):
        """
        Enable all optimizations.

        Use this to quickly enable all features after successful testing.

        Example:
            >>> FeatureFlags.enable_all_optimizations()
            >>> # Now running with all optimizations
        """
        cls.ENABLE_PARSE_CACHE = True
        cls.ENABLE_BATCHING = True
        cls.ENABLE_NEO4J_BATCHING = True
        cls.ENABLE_PARALLEL_WORKERS = True
        cls.ENABLE_METRICS = True

        logger.info("✅ All optimizations enabled")

    @classmethod
    def print_status(cls):
        """Print current feature flag status to console."""
        status = cls.get_status()

        print("\n" + "=" * 70)
        print("FEATURE FLAGS STATUS")
        print("=" * 70)

        for feature, enabled in status.items():
            status_icon = "[ON]" if enabled else "[OFF]"
            status_text = "ENABLED" if enabled else "DISABLED"
            print(f"{status_icon} {feature.upper().replace('_', ' ')}: {status_text}")

        print("=" * 70)

        # Calculate optimization level
        enabled_count = sum(status.values())
        total_count = len(status)
        optimization_level = (enabled_count / total_count) * 100

        if optimization_level == 100:
            print("** Running at FULL OPTIMIZATION (10-15x throughput)")
        elif optimization_level >= 75:
            print(f"** Running at {optimization_level:.0f}% optimization")
        elif optimization_level >= 50:
            print(f"!! Running at {optimization_level:.0f}% optimization")
        elif optimization_level > 0:
            print(
                f"!! Running at {optimization_level:.0f}% optimization (degraded performance)"
            )
        else:
            print("!! Running in BASELINE MODE (no optimizations)")

        print("=" * 70 + "\n")

    @classmethod
    def validate_configuration(cls) -> tuple[bool, list[str]]:
        """
        Validate feature flag configuration for potential issues.

        Returns:
            Tuple of (is_valid, warnings) where:
            - is_valid: True if configuration is valid
            - warnings: List of warning messages

        Example:
            >>> valid, warnings = FeatureFlags.validate_configuration()
            >>> if not valid:
            ...     print(f"Invalid configuration: {warnings}")
        """
        warnings = []

        # Check for suboptimal configurations
        if cls.ENABLE_PARALLEL_WORKERS and not cls.ENABLE_BATCHING:
            warnings.append(
                "Parallel workers enabled without batching may cause event storms. "
                "Consider enabling FEATURE_BATCHING for optimal performance."
            )

        if cls.ENABLE_NEO4J_BATCHING and not cls.ENABLE_BATCHING:
            warnings.append(
                "Neo4j batching works best with event batching enabled. "
                "Consider enabling FEATURE_BATCHING."
            )

        if cls.ENABLE_PARSE_CACHE and not cls.ENABLE_BATCHING:
            warnings.append(
                "Parse cache effectiveness increases with batching. "
                "Consider enabling FEATURE_BATCHING for better hit rates."
            )

        if not cls.ENABLE_METRICS:
            warnings.append(
                "Metrics collection disabled - you won't have visibility into "
                "performance. Consider enabling FEATURE_METRICS for production."
            )

        # All disabled is valid but warn
        if not any(cls.get_status().values()):
            warnings.append(
                "All optimizations disabled - running in baseline mode. "
                "Performance will be significantly degraded (1x throughput)."
            )

        is_valid = True  # Currently all configurations are valid, just with warnings
        return is_valid, warnings


def get_feature_flags() -> FeatureFlags:
    """
    Get feature flags instance.

    This is a convenience function for dependency injection.

    Returns:
        FeatureFlags class (singleton pattern)

    Example:
        >>> flags = get_feature_flags()
        >>> if flags.ENABLE_PARSE_CACHE:
        ...     # Use cache
    """
    return FeatureFlags


# Print status on module import (useful for debugging)
if __name__ == "__main__":
    FeatureFlags.print_status()

    # Validate configuration
    valid, warnings = FeatureFlags.validate_configuration()
    if warnings:
        print("⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
