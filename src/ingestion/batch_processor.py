"""
Batch File Processing - Event queue with debouncing for file watching.

This module provides batched event processing to reduce duplicate work
and improve efficiency when watching for file changes.
"""

import asyncio
import logging
import time
from typing import Callable, Set, Optional, Dict, Any

from src.utils import metrics

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Batches file change events with configurable debounce and size thresholds.

    Features:
    - Event deduplication (unique file paths within window)
    - Debounce timer (default: 5 seconds)
    - Batch size threshold (default: 50 files)
    - Manual flush support
    - Async/await support for non-blocking operation
    """

    def __init__(
        self,
        process_callback: Callable,
        debounce_window: float = 5.0,
        batch_size_threshold: int = 50,
        enable_batching: bool = True,
    ):
        """
        Initialize BatchProcessor.

        Args:
            process_callback: Async function to process batched file paths
            debounce_window: Debounce timer in seconds (default: 5.0)
            batch_size_threshold: Max files before auto-flush (default: 50)
            enable_batching: Enable batching (default: True)
        """
        self.process_callback = process_callback
        self.debounce_window = debounce_window
        self.batch_size_threshold = batch_size_threshold
        self.enable_batching = enable_batching

        # Event queue and deduplication set
        self._pending_files: Set[str] = set()
        self._event_timestamps: Dict[str, float] = {}

        # Debounce timer task
        self._debounce_task: Optional[asyncio.Task] = None
        self._last_event_time: float = 0

        # Statistics
        self._events_received = 0
        self._events_deduplicated = 0
        self._batches_processed = 0

    async def add_event(self, file_path: str):
        """
        Add file change event to the batch queue.

        Args:
            file_path: Absolute path to changed file
        """
        self._events_received += 1
        current_time = time.time()

        # Deduplication: skip if already in pending set
        if file_path in self._pending_files:
            self._events_deduplicated += 1
            logger.debug(f"Deduplicated event for {file_path}")
            return

        # Add to pending set
        self._pending_files.add(file_path)
        self._event_timestamps[file_path] = current_time
        self._last_event_time = current_time

        logger.debug(
            f"Event added: {file_path} (queue size: {len(self._pending_files)})"
        )

        if not self.enable_batching:
            # Immediate processing mode
            await self._process_immediately(file_path)
            return

        # Check batch size threshold
        if len(self._pending_files) >= self.batch_size_threshold:
            logger.info(
                f"Batch size threshold reached ({self.batch_size_threshold}). "
                "Triggering immediate flush."
            )
            await self.flush_now()
            return

        # Start/restart debounce timer
        await self._reset_debounce_timer()

    async def _process_immediately(self, file_path: str):
        """Process single file immediately (real-time mode)."""
        self._pending_files.discard(file_path)
        self._event_timestamps.pop(file_path, None)

        try:
            await self.process_callback([file_path])
            logger.debug(f"Processed immediately: {file_path}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    async def _reset_debounce_timer(self):
        """Reset debounce timer."""
        if self._debounce_task and not self._debounce_task.done():
            return

        self._debounce_task = asyncio.create_task(self._debounce_timer())

    async def _debounce_timer(self):
        """Debounce timer - flushes batch after window expires."""
        try:
            while True:
                await asyncio.sleep(self.debounce_window)

                if time.time() - self._last_event_time < self.debounce_window:
                    continue

                if self._pending_files:
                    logger.debug(
                        f"Debounce window ({self.debounce_window}s) expired. "
                        f"Flushing {len(self._pending_files)} files."
                    )
                    await self.flush_now()

                if not self._pending_files:
                    break

        except asyncio.CancelledError:
            # Timer was reset - this is normal
            pass
        finally:
            self._debounce_task = None
            if self._pending_files:
                await self._reset_debounce_timer()

    async def flush_now(self):
        """
        Manually flush all pending file events immediately.

        This should be called when stopping the file watcher or when
        forcing immediate processing.
        """
        if not self._pending_files:
            return

        # Extract pending files
        files_to_process = list(self._pending_files)
        file_count = len(files_to_process)

        # Clear pending set
        self._pending_files.clear()
        self._event_timestamps.clear()

        # Process batch
        logger.info(f"Flushing batch of {file_count} files")
        self._batches_processed += 1

        # Record batch size metric
        metrics.BATCH_SIZE_HISTOGRAM.observe(file_count)

        start_time = time.time()
        try:
            await self.process_callback(files_to_process)

            # Record batch processing duration
            duration = time.time() - start_time
            metrics.BATCH_PROCESSING_DURATION_SECONDS.observe(duration)

            logger.info(
                f"Successfully processed batch of {file_count} files in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Error processing batch of {file_count} files: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get batch processor statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "events_received": self._events_received,
            "events_deduplicated": self._events_deduplicated,
            "pending_files": len(self._pending_files),
            "batches_processed": self._batches_processed,
            "deduplication_rate_percent": (
                round(self._events_deduplicated / self._events_received * 100, 2)
                if self._events_received > 0
                else 0
            ),
            "debounce_window_seconds": self.debounce_window,
            "batch_size_threshold": self.batch_size_threshold,
            "batching_enabled": self.enable_batching,
        }

    async def shutdown(self):
        """Gracefully shutdown the batch processor."""
        logger.info("Shutting down batch processor")

        # Flush remaining events
        await self.flush_now()

        # Cancel debounce timer
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        logger.info("Batch processor shutdown complete")


# Example usage
async def example_callback(file_paths):
    """Example callback for processing batched files."""
    print(f"Processing batch of {len(file_paths)} files:")
    for path in file_paths:
        print(f"  - {path}")


async def main():
    """Example usage of BatchProcessor."""
    processor = BatchProcessor(
        process_callback=example_callback, debounce_window=2.0, batch_size_threshold=5
    )

    # Simulate file events
    print("Simulating file events...")
    await processor.add_event("file1.sql")
    await asyncio.sleep(0.5)
    await processor.add_event("file2.sql")
    await asyncio.sleep(0.5)
    await processor.add_event("file1.sql")  # Duplicate - should be deduplicated
    await asyncio.sleep(0.5)
    await processor.add_event("file3.sql")

    # Wait for debounce window to expire
    print(f"Waiting for debounce window ({processor.debounce_window}s)...")
    await asyncio.sleep(processor.debounce_window + 0.5)

    # Print statistics
    print("\nStatistics:")
    stats = processor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    await processor.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
