"""Unit tests for BatchProcessor."""

import asyncio
import unittest
from unittest.mock import AsyncMock
from src.ingestion.batch_processor import BatchProcessor


class TestBatchProcessor(unittest.IsolatedAsyncioTestCase):
    """Test BatchProcessor functionality."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create mock callback
        self.mock_callback = AsyncMock()

        # Create processor with short timings for faster tests
        self.processor = BatchProcessor(
            process_callback=self.mock_callback,
            debounce_window=0.1,  # 100ms for testing
            batch_size_threshold=3,
        )

    async def asyncTearDown(self):
        """Clean up test fixtures."""
        await self.processor.shutdown()

    async def test_add_event_accumulates(self):
        """Test events accumulate in pending set."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file2.sql")

        self.assertEqual(len(self.processor._pending_files), 2)
        self.assertIn("file1.sql", self.processor._pending_files)
        self.assertIn("file2.sql", self.processor._pending_files)

    async def test_event_deduplication(self):
        """Test duplicate events are deduplicated."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file1.sql")

        self.assertEqual(len(self.processor._pending_files), 1)
        self.assertEqual(self.processor._events_received, 3)
        self.assertEqual(self.processor._events_deduplicated, 2)

    async def test_debounce_timer_flush(self):
        """Test debounce timer triggers flush."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file2.sql")

        # Wait for debounce window to expire
        await asyncio.sleep(self.processor.debounce_window + 0.05)

        # Callback should have been called once with both files
        self.mock_callback.assert_called_once()
        args = self.mock_callback.call_args[0][0]
        self.assertEqual(len(args), 2)
        self.assertIn("file1.sql", args)
        self.assertIn("file2.sql", args)

    async def test_batch_size_threshold_flush(self):
        """Test batch size threshold triggers immediate flush."""
        # Add exactly threshold number of files
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file2.sql")
        await self.processor.add_event("file3.sql")

        # Should flush immediately (threshold=3)
        # Give it a moment to process
        await asyncio.sleep(0.01)

        self.mock_callback.assert_called_once()
        args = self.mock_callback.call_args[0][0]
        self.assertEqual(len(args), 3)

    async def test_manual_flush(self):
        """Test manual flush trigger."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file2.sql")

        # Manually flush before debounce expires
        await self.processor.flush_now()

        self.mock_callback.assert_called_once()
        self.assertEqual(len(self.processor._pending_files), 0)

    async def test_batching_disabled_immediate_processing(self):
        """Test immediate processing when batching disabled."""
        processor = BatchProcessor(
            process_callback=self.mock_callback, enable_batching=False
        )

        await processor.add_event("file1.sql")
        await processor.add_event("file2.sql")

        # Should process immediately, not batch
        self.assertEqual(self.mock_callback.call_count, 2)

        # First call with file1
        args1 = self.mock_callback.call_args_list[0][0][0]
        self.assertEqual(args1, ["file1.sql"])

        # Second call with file2
        args2 = self.mock_callback.call_args_list[1][0][0]
        self.assertEqual(args2, ["file2.sql"])

        await processor.shutdown()

    async def test_flush_clears_pending_files(self):
        """Test flush clears pending files."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file2.sql")

        self.assertEqual(len(self.processor._pending_files), 2)

        await self.processor.flush_now()

        self.assertEqual(len(self.processor._pending_files), 0)
        self.assertEqual(len(self.processor._event_timestamps), 0)

    async def test_flush_empty_batch_no_callback(self):
        """Test flush with no pending files doesn't call callback."""
        await self.processor.flush_now()

        self.mock_callback.assert_not_called()

    async def test_get_stats(self):
        """Test statistics reporting."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file1.sql")  # Duplicate
        await self.processor.add_event("file2.sql")

        stats = self.processor.get_stats()

        self.assertEqual(stats["events_received"], 3)
        self.assertEqual(stats["events_deduplicated"], 1)
        self.assertEqual(stats["pending_files"], 2)
        self.assertEqual(stats["deduplication_rate_percent"], 33.33)
        self.assertEqual(stats["debounce_window_seconds"], 0.1)
        self.assertEqual(stats["batch_size_threshold"], 3)
        self.assertTrue(stats["batching_enabled"])

    async def test_shutdown_flushes_pending_events(self):
        """Test shutdown flushes remaining events."""
        await self.processor.add_event("file1.sql")
        await self.processor.add_event("file2.sql")

        await self.processor.shutdown()

        # Should have flushed pending events
        self.mock_callback.assert_called_once()
        self.assertEqual(len(self.processor._pending_files), 0)

    async def test_debounce_timer_reset_on_new_event(self):
        """Test debounce timer resets when new events arrive."""
        await self.processor.add_event("file1.sql")
        await asyncio.sleep(0.05)  # Half of debounce window

        # Add another event - should reset timer
        await self.processor.add_event("file2.sql")
        await asyncio.sleep(0.05)  # Another half window

        # Callback should not have been called yet
        self.mock_callback.assert_not_called()

        # Wait for full window from last event
        await asyncio.sleep(0.1)

        # Now it should have been called
        self.mock_callback.assert_called_once()

    async def test_callback_error_handling(self):
        """Test error handling in callback."""
        error_callback = AsyncMock(side_effect=Exception("Processing error"))

        processor = BatchProcessor(process_callback=error_callback, debounce_window=0.1)

        await processor.add_event("file1.sql")

        # Flush should raise the exception
        with self.assertRaises(Exception) as context:
            await processor.flush_now()

        self.assertEqual(str(context.exception), "Processing error")

        await processor.shutdown()

    async def test_statistics_batches_processed(self):
        """Test batches_processed statistic increments."""
        await self.processor.add_event("file1.sql")
        await self.processor.flush_now()

        stats = self.processor.get_stats()
        self.assertEqual(stats["batches_processed"], 1)

        await self.processor.add_event("file2.sql")
        await self.processor.flush_now()

        stats = self.processor.get_stats()
        self.assertEqual(stats["batches_processed"], 2)


if __name__ == "__main__":
    unittest.main()
