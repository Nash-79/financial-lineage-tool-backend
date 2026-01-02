"""
Worker Pool - Async worker pool for parallel SQL file processing.

This module provides a priority-based worker pool using asyncio and ProcessPoolExecutor
for efficient parallel processing of CPU-bound SQL parsing tasks.
"""

import asyncio
import logging
import os
import psutil
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

from src.utils import metrics

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Task priority levels (lower number = higher priority)."""

    CRITICAL = 1
    NORMAL = 2
    BATCH = 3


@dataclass(order=True)
class WorkItem:
    """Priority queue work item."""

    priority: int
    file_path: str = field(compare=False)
    callback: Callable = field(compare=False)
    created_at: datetime = field(default_factory=datetime.now, compare=False)


class WorkerPool:
    """
    Async worker pool for parallel SQL file processing.

    Features:
    - Priority-based task queue (critical, normal, batch)
    - ProcessPoolExecutor for CPU-bound parsing
    - Configurable worker count
    - Back-pressure handling
    - Graceful shutdown
    - Statistics tracking
    """

    def __init__(
        self,
        num_workers: Optional[int] = None,
        max_queue_size: int = 200,
        memory_threshold_percent: float = 80.0,
        enable_back_pressure: bool = True,
    ):
        """
        Initialize worker pool.

        Args:
            num_workers: Number of workers (default: min(4, cpu_count()))
            max_queue_size: Maximum queue size before back-pressure (default: 200)
            memory_threshold_percent: Memory usage threshold for back-pressure (default: 80%)
            enable_back_pressure: Enable back-pressure handling (default: True)
        """
        # Determine worker count
        cpu_count = os.cpu_count() or 1
        self.num_workers = num_workers or min(4, cpu_count)

        self.max_queue_size = max_queue_size
        self.memory_threshold = memory_threshold_percent
        self.enable_back_pressure = enable_back_pressure

        # Priority queue
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # ProcessPoolExecutor for CPU-bound tasks
        self.executor: Optional[ProcessPoolExecutor] = None

        # Worker tasks
        self.workers: list[asyncio.Task] = []

        # State tracking
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Statistics
        self._tasks_submitted = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._back_pressure_events = 0

        logger.info(f"Worker pool initialized with {self.num_workers} workers")

    async def start(self):
        """Start the worker pool."""
        if self._running:
            logger.warning("Worker pool already running")
            return

        self._running = True
        self._shutdown_event.clear()

        # Create ProcessPoolExecutor
        self.executor = ProcessPoolExecutor(max_workers=self.num_workers)

        # Start worker tasks
        self.workers = [
            asyncio.create_task(self._worker(i)) for i in range(self.num_workers)
        ]

        logger.info(f"Worker pool started with {self.num_workers} workers")

    async def submit(
        self, file_path: str, callback: Callable, priority: Priority = Priority.NORMAL
    ):
        """
        Submit task to worker pool.

        Args:
            file_path: Path to file to process
            callback: Async callback function to execute
            priority: Task priority (CRITICAL, NORMAL, BATCH)
        """
        # Check back-pressure
        if self.enable_back_pressure:
            await self._check_back_pressure()

        # Create work item
        work_item = WorkItem(
            priority=priority.value, file_path=file_path, callback=callback
        )

        # Add to queue
        await self.task_queue.put(work_item)
        self._tasks_submitted += 1

        # Update queue size metric
        metrics.QUEUE_SIZE.set(self.task_queue.qsize())

        logger.debug(
            f"Task submitted: {file_path} (priority={priority.name}, "
            f"queue_size={self.task_queue.qsize()})"
        )

    async def _check_back_pressure(self):
        """Check and apply back-pressure if needed."""
        # Check queue size
        if self.task_queue.qsize() >= self.max_queue_size:
            self._back_pressure_events += 1
            logger.warning(
                f"Back-pressure: Queue size ({self.task_queue.qsize()}) "
                f"exceeded threshold ({self.max_queue_size}). Pausing..."
            )

            # Wait until queue drains
            while self.task_queue.qsize() >= self.max_queue_size // 2:
                await asyncio.sleep(0.5)

            logger.info("Back-pressure released: Queue drained")

        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent >= self.memory_threshold:
            self._back_pressure_events += 1
            logger.warning(
                f"Back-pressure: Memory usage ({memory.percent:.1f}%) "
                f"exceeded threshold ({self.memory_threshold}%). Pausing..."
            )

            # Wait until memory drops
            while psutil.virtual_memory().percent >= self.memory_threshold - 10:
                await asyncio.sleep(1.0)

            logger.info("Back-pressure released: Memory usage normalized")

    async def _worker(self, worker_id: int):
        """
        Worker coroutine that processes tasks from the queue.

        Args:
            worker_id: Worker identifier
        """
        logger.debug(f"Worker {worker_id} started")

        # Increment active workers
        metrics.ACTIVE_WORKERS.inc()

        try:
            while self._running or not self.task_queue.empty():
                try:
                    # Get next task (with timeout to check shutdown)
                    try:
                        work_item = await asyncio.wait_for(
                            self.task_queue.get(), timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        # Check if we should shutdown
                        if not self._running and self.task_queue.empty():
                            break
                        continue

                    # Process task
                    logger.debug(
                        f"Worker {worker_id} processing: {work_item.file_path} "
                        f"(priority={work_item.priority})"
                    )

                    try:
                        # Execute callback
                        await work_item.callback(work_item.file_path)
                        self._tasks_completed += 1
                        metrics.FILES_PROCESSED_TOTAL.inc()
                        logger.debug(
                            f"Worker {worker_id} completed: {work_item.file_path}"
                        )

                    except Exception as e:
                        self._tasks_failed += 1
                        metrics.FILES_FAILED_TOTAL.inc()
                        logger.error(
                            f"Worker {worker_id} failed to process {work_item.file_path}: {e}",
                            exc_info=True,
                        )

                    finally:
                        self.task_queue.task_done()
                        # Update queue size after processing
                        metrics.QUEUE_SIZE.set(self.task_queue.qsize())

                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}", exc_info=True)

        finally:
            # Decrement active workers
            metrics.ACTIVE_WORKERS.dec()
            logger.debug(f"Worker {worker_id} stopped")

    async def shutdown(self, wait_for_completion: bool = True):
        """
        Gracefully shutdown the worker pool.

        Args:
            wait_for_completion: Wait for pending tasks to complete
        """
        if not self._running:
            logger.warning("Worker pool not running")
            return

        logger.info("Shutting down worker pool...")
        self._running = False

        if wait_for_completion:
            # Wait for queue to drain
            if not self.task_queue.empty():
                logger.info(f"Waiting for {self.task_queue.qsize()} pending tasks...")
                await self.task_queue.join()
                logger.info("All pending tasks completed")

        # Cancel workers
        for worker in self.workers:
            if not worker.done():
                worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)

        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None

        self._shutdown_event.set()
        logger.info("Worker pool shutdown complete")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get worker pool statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "num_workers": self.num_workers,
            "queue_size": self.task_queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "tasks_submitted": self._tasks_submitted,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "tasks_pending": self._tasks_submitted
            - self._tasks_completed
            - self._tasks_failed,
            "back_pressure_events": self._back_pressure_events,
            "success_rate_percent": (
                round(self._tasks_completed / self._tasks_submitted * 100, 2)
                if self._tasks_submitted > 0
                else 0
            ),
            "memory_usage_percent": psutil.virtual_memory().percent,
            "running": self._running,
        }


# Example usage
async def example_task(file_path: str):
    """Example task for processing a file."""
    logger.info(f"Processing file: {file_path}")
    # Simulate CPU-bound work
    await asyncio.sleep(0.5)
    logger.info(f"Completed file: {file_path}")


async def main():
    """Example usage of WorkerPool."""
    logging.basicConfig(level=logging.INFO)

    # Create worker pool
    pool = WorkerPool(num_workers=2, max_queue_size=10)

    await pool.start()

    # Submit tasks with different priorities
    await pool.submit("critical_file.sql", example_task, Priority.CRITICAL)
    await pool.submit("normal_file1.sql", example_task, Priority.NORMAL)
    await pool.submit("normal_file2.sql", example_task, Priority.NORMAL)
    await pool.submit("batch_file.sql", example_task, Priority.BATCH)

    # Wait a bit for processing
    await asyncio.sleep(3)

    # Print statistics
    print("\nWorker Pool Statistics:")
    stats = pool.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Shutdown
    await pool.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
