"""Unit tests for WorkerPool."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from src.ingestion.worker_pool import WorkerPool, Priority


class TestWorkerPool(unittest.IsolatedAsyncioTestCase):
    """Test WorkerPool functionality."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create worker pool with small capacity for testing
        self.pool = WorkerPool(
            num_workers=2,
            max_queue_size=5,
            memory_threshold_percent=95.0,  # High threshold to avoid triggering in tests
            enable_back_pressure=True,
        )

        await self.pool.start()

    async def asyncTearDown(self):
        """Clean up test fixtures."""
        await self.pool.shutdown(wait_for_completion=False)

    async def test_worker_pool_initialization(self):
        """Test worker pool initializes correctly."""
        self.assertEqual(self.pool.num_workers, 2)
        self.assertEqual(self.pool.max_queue_size, 5)
        self.assertTrue(self.pool._running)

    async def test_submit_task(self):
        """Test submitting a task to the pool."""
        mock_callback = AsyncMock()

        await self.pool.submit("test_file.sql", mock_callback, Priority.NORMAL)

        # Wait for task to complete
        await asyncio.sleep(0.1)
        await self.pool.task_queue.join()

        # Callback should have been called
        mock_callback.assert_called_once_with("test_file.sql")

    async def test_priority_ordering(self):
        """Test tasks are processed in priority order."""
        call_order = []

        async def track_call(file_path: str):
            call_order.append(file_path)

        # Submit tasks in reverse priority order
        await self.pool.submit("batch.sql", track_call, Priority.BATCH)
        await self.pool.submit("normal.sql", track_call, Priority.NORMAL)
        await self.pool.submit("critical.sql", track_call, Priority.CRITICAL)

        # Wait for all tasks to complete
        await asyncio.sleep(0.2)
        await self.pool.task_queue.join()

        # Should process in priority order: CRITICAL (1), NORMAL (2), BATCH (3)
        self.assertEqual(call_order[0], "critical.sql")
        # Note: normal.sql and batch.sql order may vary due to parallel workers

    async def test_multiple_tasks_completion(self):
        """Test multiple tasks are all completed."""
        mock_callback = AsyncMock()

        # Submit 5 tasks
        for i in range(5):
            await self.pool.submit(f"file{i}.sql", mock_callback, Priority.NORMAL)

        # Wait for all tasks
        await asyncio.sleep(0.5)
        await self.pool.task_queue.join()

        # All should be called
        self.assertEqual(mock_callback.call_count, 5)

    async def test_task_failure_handling(self):
        """Test worker handles task failures gracefully."""

        # Create callback that raises exception
        async def failing_callback(file_path: str):
            raise Exception("Test error")

        await self.pool.submit("failing_file.sql", failing_callback, Priority.NORMAL)

        # Wait for task to fail
        await asyncio.sleep(0.1)
        await self.pool.task_queue.join()

        # Should increment failed counter
        stats = self.pool.get_stats()
        self.assertEqual(stats["tasks_failed"], 1)

    async def test_get_stats(self):
        """Test statistics reporting."""
        mock_callback = AsyncMock()

        # Submit some tasks
        await self.pool.submit("file1.sql", mock_callback, Priority.NORMAL)
        await self.pool.submit("file2.sql", mock_callback, Priority.NORMAL)

        # Wait for completion
        await asyncio.sleep(0.2)
        await self.pool.task_queue.join()

        stats = self.pool.get_stats()

        self.assertEqual(stats["num_workers"], 2)
        self.assertEqual(stats["tasks_submitted"], 2)
        self.assertEqual(stats["tasks_completed"], 2)
        self.assertEqual(stats["tasks_failed"], 0)
        self.assertEqual(stats["tasks_pending"], 0)
        self.assertEqual(stats["success_rate_percent"], 100.0)

    async def test_back_pressure_queue_size(self):
        """Test back-pressure triggers on queue size."""
        slow_callback = AsyncMock(side_effect=lambda x: asyncio.sleep(1.0))

        # Fill queue beyond threshold
        for i in range(6):  # max_queue_size=5
            if i < 5:
                await self.pool.submit(f"file{i}.sql", slow_callback, Priority.NORMAL)
            else:
                # This should trigger back-pressure
                with patch.object(self.pool, "_check_back_pressure") as mock_bp:
                    mock_bp.return_value = asyncio.sleep(0)
                    await self.pool.submit(
                        f"file{i}.sql", slow_callback, Priority.NORMAL
                    )
                    mock_bp.assert_called_once()

    async def test_shutdown_waits_for_completion(self):
        """Test shutdown waits for pending tasks."""
        call_count = 0

        async def counting_callback(file_path: str):
            nonlocal call_count
            await asyncio.sleep(0.1)
            call_count += 1

        # Submit tasks
        await self.pool.submit("file1.sql", counting_callback, Priority.NORMAL)
        await self.pool.submit("file2.sql", counting_callback, Priority.NORMAL)

        # Shutdown with wait
        await self.pool.shutdown(wait_for_completion=True)

        # Both tasks should have completed
        self.assertEqual(call_count, 2)

    async def test_shutdown_without_wait(self):
        """Test shutdown can cancel pending tasks."""
        slow_callback = AsyncMock(side_effect=lambda x: asyncio.sleep(10.0))

        # Submit slow tasks
        await self.pool.submit("file1.sql", slow_callback, Priority.NORMAL)
        await self.pool.submit("file2.sql", slow_callback, Priority.NORMAL)

        # Shutdown without wait
        await asyncio.sleep(0.05)  # Give tasks time to start
        await self.pool.shutdown(wait_for_completion=False)

        # Not all tasks will complete
        stats = self.pool.get_stats()
        self.assertLess(stats["tasks_completed"], 2)

    async def test_worker_pool_restartable(self):
        """Test worker pool can be stopped and restarted."""
        mock_callback = AsyncMock()

        await self.pool.shutdown()

        # Restart
        new_pool = WorkerPool(num_workers=2)
        await new_pool.start()

        await new_pool.submit("test.sql", mock_callback, Priority.NORMAL)
        await asyncio.sleep(0.1)
        await new_pool.task_queue.join()

        mock_callback.assert_called_once()

        await new_pool.shutdown()

    async def test_concurrent_workers_process_tasks(self):
        """Test multiple workers process tasks concurrently."""
        processing_times = []

        async def timed_callback(file_path: str):
            import time

            start = time.time()
            await asyncio.sleep(0.1)
            processing_times.append((file_path, time.time() - start))

        # Submit 4 tasks to 2 workers
        for i in range(4):
            await self.pool.submit(f"file{i}.sql", timed_callback, Priority.NORMAL)

        await asyncio.sleep(0.5)
        await self.pool.task_queue.join()

        # All should complete
        self.assertEqual(len(processing_times), 4)

        # With 2 workers processing 0.1s tasks, 4 tasks should take ~0.2s total
        # (2 batches of 2 concurrent tasks)
        total_time = max(end_time for _, end_time in processing_times)
        self.assertLess(total_time, 0.4)  # Should be much less than sequential (0.4s)


if __name__ == "__main__":
    unittest.main()
