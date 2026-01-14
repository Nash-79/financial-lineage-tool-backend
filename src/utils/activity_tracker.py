"""
Activity Tracking System for Financial Lineage Tool

Tracks API usage, query performance, and system metrics for monitoring and analytics.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
import json


@dataclass
class ActivityEvent:
    """Represents a single activity event."""

    timestamp: str
    event_type: str  # "query", "ingest", "health_check", "error"
    endpoint: str
    latency_ms: float
    status: str  # "success", "error"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "endpoint": self.endpoint,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass
class SessionMetrics:
    """Aggregated metrics for a session."""

    session_start: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_queries: int = 0
    total_ingestions: int = 0
    total_health_checks: int = 0
    avg_latency_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    endpoint_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_start": self.session_start,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_queries": self.total_queries,
            "total_ingestions": self.total_ingestions,
            "total_health_checks": self.total_health_checks,
            "avg_latency_ms": self.avg_latency_ms,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "endpoint_counts": dict(self.endpoint_counts),
            "error_types": dict(self.error_types),
        }


class ActivityTracker:
    """
    Tracks system activity and provides metrics.

    Features:
    - Event logging with metadata
    - Session-level aggregation
    - Real-time metrics calculation
    - Redis persistence (optional)
    - Export to JSON
    """

    def __init__(self, redis_client=None, max_events: int = 10000):
        """
        Initialize activity tracker.

        Args:
            redis_client: Optional Redis client for persistence
            max_events: Maximum number of events to keep in memory
        """
        self.redis_client = redis_client
        self.max_events = max_events
        self.session_start = datetime.utcnow().isoformat()

        # In-memory storage
        self.events: List[ActivityEvent] = []
        self.metrics = SessionMetrics(session_start=self.session_start)

        # Running calculations
        self._latency_sum = 0.0
        self._latency_count = 0

    async def track_event(
        self,
        event_type: str,
        endpoint: str,
        latency_ms: float,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track an activity event.

        Args:
            event_type: Type of event (query, ingest, health_check, error)
            endpoint: API endpoint called
            latency_ms: Request latency in milliseconds
            status: "success" or "error"
            metadata: Additional event metadata
        """
        # Create event
        event = ActivityEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            endpoint=endpoint,
            latency_ms=latency_ms,
            status=status,
            metadata=metadata or {},
        )

        # Store in memory
        self.events.append(event)
        if len(self.events) > self.max_events:
            # Remove oldest event
            self.events.pop(0)

        # Update metrics
        self._update_metrics(event)

        # Persist to Redis if available
        if self.redis_client:
            await self._persist_event(event)

    def _update_metrics(self, event: ActivityEvent) -> None:
        """Update aggregated metrics based on event."""
        self.metrics.total_requests += 1

        if event.status == "success":
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
            error_type = event.metadata.get("error_type", "unknown")
            self.metrics.error_types[error_type] += 1

        # Track by event type
        if event.event_type == "query":
            self.metrics.total_queries += 1
        elif event.event_type == "ingest":
            self.metrics.total_ingestions += 1
        elif event.event_type == "health_check":
            self.metrics.total_health_checks += 1

        # Track endpoint
        self.metrics.endpoint_counts[event.endpoint] += 1

        # Update latency average
        self._latency_sum += event.latency_ms
        self._latency_count += 1
        self.metrics.avg_latency_ms = self._latency_sum / self._latency_count

        # Track cache metrics if available
        if "cache_hit" in event.metadata:
            if event.metadata["cache_hit"]:
                self.metrics.cache_hits += 1
            else:
                self.metrics.cache_misses += 1

    async def _persist_event(self, event: ActivityEvent) -> None:
        """Persist event to Redis."""
        if not self.redis_client:
            return

        try:
            # Store event in a Redis list (FIFO queue)
            event_key = "activity:events"
            await self.redis_client.lpush(event_key, json.dumps(event.to_dict()))

            # Trim to keep only recent events
            await self.redis_client.ltrim(event_key, 0, self.max_events - 1)

            # Update session metrics in Redis
            metrics_key = "activity:session_metrics"

            await self.redis_client.set(
                metrics_key, json.dumps(self.metrics.to_dict()), ex=86400  # 24 hour TTL
            )

        except Exception as e:
            # Don't fail the request if tracking fails
            import traceback

            traceback.print_exc()
            print(f"[!] Failed to persist activity event: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current session metrics.

        Returns:
            Dictionary with aggregated metrics
        """
        # Calculate cache hit rate
        total_cache_requests = self.metrics.cache_hits + self.metrics.cache_misses
        cache_hit_rate = (
            self.metrics.cache_hits / total_cache_requests
            if total_cache_requests > 0
            else 0.0
        )

        # Calculate success rate
        success_rate = (
            self.metrics.successful_requests / self.metrics.total_requests
            if self.metrics.total_requests > 0
            else 0.0
        )

        return {
            "session_start": self.metrics.session_start,
            "uptime_seconds": (
                datetime.utcnow() - datetime.fromisoformat(self.session_start)
            ).total_seconds(),
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": success_rate,
            "total_queries": self.metrics.total_queries,
            "total_ingestions": self.metrics.total_ingestions,
            "total_health_checks": self.metrics.total_health_checks,
            "avg_latency_ms": round(self.metrics.avg_latency_ms, 2),
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "top_endpoints": dict(
                sorted(
                    self.metrics.endpoint_counts.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
            "error_types": dict(self.metrics.error_types),
        }

    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent activity events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events (most recent first)
        """
        recent = self.events[-limit:][::-1]  # Reverse to get most recent first
        return [event.to_dict() for event in recent]

    async def get_events_from_redis(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent events from Redis.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events from Redis
        """
        if not self.redis_client:
            return []

        try:
            events_json = await self.redis_client.lrange(
                "activity:events", 0, limit - 1
            )
            return [json.loads(e) for e in events_json]
        except Exception as e:
            print(f"[!] Failed to retrieve events from Redis: {e}")
            return []

    def reset_metrics(self) -> None:
        """Reset all metrics and events (useful for testing)."""
        self.session_start = datetime.utcnow().isoformat()
        self.events.clear()
        self.metrics = SessionMetrics(session_start=self.session_start)
        self._latency_sum = 0.0
        self._latency_count = 0
