"""
Simplified integration tests for parallel processing components.

Tests the integration between BatchProcessor and WorkerPool without
full file watcher complexity.
"""

import asyncio
import unittest
from src.ingestion.batch_processor import BatchProcessor
from src.ingestion.worker_pool import WorkerPool, Priority


class TestParallelComponentIntegration(unittest.IsolatedAsyncioTestCase):
    """Test integration between batch processor and worker pool."""

    async def test_batch_processor_to_worker_pool_flow(self):
        """Test complete flow from batch processor to worker pool."""
        processed_items = []

        # Create mock callback that adds to worker pool
        async def process_callback(file_path: str):
            """Process a single file."""
            await asyncio.sleep(0.05)  # Simulate work
            processed_items.append(file_path)

        # Create worker pool
        worker_pool = WorkerPool(num_workers=2, max_queue_size=10)
        await worker_pool.start()

        # Create batch callback that submits to worker pool
        async def batch_callback(file_paths):
            """Submit batch to worker pool."""
            for file_path in file_paths:
                await worker_pool.submit(file_path, process_callback, Priority.NORMAL)

        # Create batch processor
        batch_processor = BatchProcessor(
            process_callback=batch_callback,
            debounce_window=0.2,
            batch_size_threshold=5,
            enable_batching=True,
        )

        # Add 10 events
        for i in range(10):
            await batch_processor.add_event(f"file_{i}.sql")

        # Wait for processing
        await asyncio.sleep(1.0)

        # Cleanup
        await batch_processor.shutdown()
        await worker_pool.shutdown(wait_for_completion=True)

        # Verify all items processed
        self.assertEqual(len(processed_items), 10)

        # Verify statistics
        batch_stats = batch_processor.get_stats()
        worker_stats = worker_pool.get_stats()

        self.assertEqual(batch_stats["events_received"], 10)
        self.assertEqual(worker_stats["tasks_completed"], 10)
        self.assertEqual(worker_stats["tasks_failed"], 0)

    async def test_deduplication_across_components(self):
        """Test that deduplication works in batch processor."""
        processed_items = []

        async def process_callback(file_path: str):
            processed_items.append(file_path)

        worker_pool = WorkerPool(num_workers=1)
        await worker_pool.start()

        async def batch_callback(file_paths):
            for file_path in file_paths:
                await worker_pool.submit(file_path, process_callback, Priority.NORMAL)

        batch_processor = BatchProcessor(
            process_callback=batch_callback, debounce_window=0.3, enable_batching=True
        )

        # Add same file 5 times
        for _ in range(5):
            await batch_processor.add_event("duplicate.sql")

        # Wait for processing
        await asyncio.sleep(0.8)

        # Cleanup
        await batch_processor.shutdown()
        await worker_pool.shutdown()

        # Should only process once
        self.assertEqual(len(processed_items), 1)

        # Verify deduplication stats
        stats = batch_processor.get_stats()
        self.assertEqual(stats["events_received"], 5)
        self.assertEqual(stats["events_deduplicated"], 4)

    async def test_batch_size_threshold_integration(self):
        """Test that batch size threshold triggers immediate processing."""
        processed_batches = []

        async def process_callback(file_path: str):
            await asyncio.sleep(0.05)

        worker_pool = WorkerPool(num_workers=2)
        await worker_pool.start()

        async def batch_callback(file_paths):
            processed_batches.append(len(file_paths))
            for file_path in file_paths:
                await worker_pool.submit(file_path, process_callback, Priority.NORMAL)

        # Set threshold at 5
        batch_processor = BatchProcessor(
            process_callback=batch_callback,
            debounce_window=5.0,  # Long debounce
            batch_size_threshold=5,
            enable_batching=True,
        )

        # Add 12 files (should trigger 2 full batches + 1 partial on shutdown)
        for i in range(12):
            await batch_processor.add_event(f"file_{i}.sql")

        # Wait less than debounce window
        await asyncio.sleep(0.5)

        # Cleanup (will flush remaining 2 files)
        await batch_processor.shutdown()
        await worker_pool.shutdown()

        # Should have at least 2 batches of 5
        self.assertGreaterEqual(len(processed_batches), 2)
        self.assertEqual(processed_batches[0], 5)
        self.assertEqual(processed_batches[1], 5)

    async def test_priority_ordering_integration(self):
        """Test that priority ordering works through the pipeline."""
        processing_order = []

        async def process_callback(file_path: str):
            processing_order.append(file_path)
            await asyncio.sleep(0.05)

        # Single worker for ordered processing
        worker_pool = WorkerPool(num_workers=1)
        await worker_pool.start()

        # Submit tasks with different priorities
        await worker_pool.submit("batch_1.sql", process_callback, Priority.BATCH)
        await worker_pool.submit("normal_1.sql", process_callback, Priority.NORMAL)
        await worker_pool.submit("critical_1.sql", process_callback, Priority.CRITICAL)
        await worker_pool.submit("batch_2.sql", process_callback, Priority.BATCH)
        await worker_pool.submit("critical_2.sql", process_callback, Priority.CRITICAL)

        # Wait for processing
        await asyncio.sleep(0.5)
        await worker_pool.task_queue.join()

        # Cleanup
        await worker_pool.shutdown()

        # Verify critical tasks processed first
        self.assertEqual(processing_order[0], "critical_1.sql")
        self.assertEqual(processing_order[1], "critical_2.sql")
        # Normal should be before batch
        normal_idx = processing_order.index("normal_1.sql")
        batch_indices = [i for i, f in enumerate(processing_order) if "batch" in f]
        self.assertTrue(all(normal_idx < idx for idx in batch_indices))

    async def test_error_handling_integration(self):
        """Test that errors are handled gracefully across components."""

        async def failing_callback(file_path: str):
            if "fail" in file_path:
                raise Exception("Simulated error")
            await asyncio.sleep(0.05)

        worker_pool = WorkerPool(num_workers=2)
        await worker_pool.start()

        async def batch_callback(file_paths):
            for file_path in file_paths:
                await worker_pool.submit(file_path, failing_callback, Priority.NORMAL)

        batch_processor = BatchProcessor(
            process_callback=batch_callback, debounce_window=0.2, enable_batching=True
        )

        # Add mix of good and bad files
        await batch_processor.add_event("good_1.sql")
        await batch_processor.add_event("fail_1.sql")
        await batch_processor.add_event("good_2.sql")
        await batch_processor.add_event("fail_2.sql")
        await batch_processor.add_event("good_3.sql")

        # Wait for processing
        await asyncio.sleep(0.8)

        # Cleanup
        await batch_processor.shutdown()
        await worker_pool.shutdown()

        # Verify stats show both success and failure
        stats = worker_pool.get_stats()
        self.assertEqual(stats["tasks_completed"], 3)
        self.assertEqual(stats["tasks_failed"], 2)
        self.assertLess(stats["success_rate_percent"], 100.0)

    async def test_statistics_consistency(self):
        """Test that statistics are consistent across components."""

        async def process_callback(file_path: str):
            await asyncio.sleep(0.02)

        worker_pool = WorkerPool(num_workers=3, max_queue_size=50)
        await worker_pool.start()

        async def batch_callback(file_paths):
            for file_path in file_paths:
                await worker_pool.submit(file_path, process_callback, Priority.NORMAL)

        batch_processor = BatchProcessor(
            process_callback=batch_callback, debounce_window=0.2, enable_batching=True
        )

        # Add 20 events
        for i in range(20):
            await batch_processor.add_event(f"file_{i}.sql")

        # Wait for processing
        await asyncio.sleep(1.0)
        await worker_pool.task_queue.join()

        # Cleanup
        await batch_processor.shutdown()
        await worker_pool.shutdown()

        # Get stats after shutdown
        batch_stats = batch_processor.get_stats()
        worker_stats = worker_pool.get_stats()

        # Verify batch processor stats
        self.assertEqual(batch_stats["events_received"], 20)
        self.assertGreater(batch_stats["batches_processed"], 0)

        # Verify worker pool stats
        self.assertEqual(worker_stats["num_workers"], 3)
        self.assertEqual(worker_stats["tasks_completed"], 20)
        self.assertEqual(worker_stats["tasks_failed"], 0)
        self.assertEqual(worker_stats["success_rate_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
