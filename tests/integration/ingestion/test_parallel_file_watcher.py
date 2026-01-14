"""Integration tests for ParallelFileWatcher - end-to-end parallel processing."""

import asyncio
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from src.ingestion.parallel_file_watcher import ParallelFileWatcher
from src.ingestion.worker_pool import Priority


class TestParallelFileWatcherIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for ParallelFileWatcher."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watch"
        self.output_dir = Path(self.temp_dir) / "output"

        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def asyncTearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    async def test_batch_and_worker_pool_integration(self):
        """Test integration between BatchProcessor and WorkerPool."""
        # Create test SQL files
        for i in range(10):
            sql_file = self.watch_dir / f"test_{i}.sql"
            sql_file.write_text(f"CREATE TABLE table_{i} (id INT);")

        # Track processed files
        processed_files = []

        # Mock the organizer
        with patch(
            "src.ingestion.parallel_file_watcher.HierarchicalOrganizer"
        ) as mock_org_class:
            mock_organizer = MagicMock()

            def track_processing(file_path):
                processed_files.append(file_path)
                return {"tables": [f"table_{len(processed_files)}.sql"]}

            mock_organizer.organize_file.side_effect = track_processing
            mock_org_class.return_value = mock_organizer

            # Create watcher
            watcher = ParallelFileWatcher(
                watch_dir=str(self.watch_dir),
                output_dir=str(self.output_dir),
                enable_batching=True,
                debounce_window=0.3,
                batch_size_threshold=5,
                num_workers=2,
            )

            # Manually initialize components (avoid signal handlers)
            watcher.loop = asyncio.get_running_loop()

            # Start worker pool
            from src.ingestion.worker_pool import WorkerPool

            watcher.worker_pool = WorkerPool(num_workers=2, max_queue_size=20)
            await watcher.worker_pool.start()

            # Start batch processor
            from src.ingestion.batch_processor import BatchProcessor

            watcher.batch_processor = BatchProcessor(
                process_callback=watcher._process_batch,
                debounce_window=0.3,
                batch_size_threshold=5,
                enable_batching=True,
            )

            # Add files to batch processor
            for i in range(10):
                await watcher.batch_processor.add_event(
                    str(self.watch_dir / f"test_{i}.sql")
                )

            # Wait for processing
            await asyncio.sleep(1.5)

            # Shutdown
            await watcher.batch_processor.shutdown()
            await watcher.worker_pool.shutdown(wait_for_completion=True)

            # Verify all files were processed
            self.assertEqual(len(processed_files), 10)

    async def test_deduplication_in_batch(self):
        """Test that batch processor deduplicates events correctly."""
        # Create test SQL file
        sql_file = self.watch_dir / "test.sql"
        sql_file.write_text("CREATE TABLE test (id INT);")

        processed_count = 0

        # Mock the organizer
        with patch(
            "src.ingestion.parallel_file_watcher.HierarchicalOrganizer"
        ) as mock_org_class:
            mock_organizer = MagicMock()

            def count_processing(file_path):
                nonlocal processed_count
                processed_count += 1
                return {"tables": ["table.sql"]}

            mock_organizer.organize_file.side_effect = count_processing
            mock_org_class.return_value = mock_organizer

            watcher = ParallelFileWatcher(
                watch_dir=str(self.watch_dir),
                output_dir=str(self.output_dir),
                enable_batching=True,
                debounce_window=0.5,
                num_workers=1,
            )

            # Manually initialize components
            watcher.loop = asyncio.get_running_loop()

            from src.ingestion.worker_pool import WorkerPool

            watcher.worker_pool = WorkerPool(num_workers=1)
            await watcher.worker_pool.start()

            from src.ingestion.batch_processor import BatchProcessor

            watcher.batch_processor = BatchProcessor(
                process_callback=watcher._process_batch,
                debounce_window=0.5,
                enable_batching=True,
            )

            # Add same file multiple times
            test_file = str(sql_file)
            await watcher.batch_processor.add_event(test_file)
            await watcher.batch_processor.add_event(test_file)
            await watcher.batch_processor.add_event(test_file)
            await watcher.batch_processor.add_event(test_file)

            # Wait for processing
            await asyncio.sleep(1.2)

            # Shutdown
            await watcher.batch_processor.shutdown()
            await watcher.worker_pool.shutdown()

            # Should only process once due to deduplication
            self.assertEqual(processed_count, 1)

            # Verify deduplication stats
            stats = watcher.batch_processor.get_stats()
            self.assertEqual(stats["events_received"], 4)
            self.assertEqual(stats["events_deduplicated"], 3)

    async def test_priority_processing_in_worker_pool(self):
        """Test that worker pool respects task priorities."""
        processing_order = []

        # Create watcher
        watcher = ParallelFileWatcher(
            watch_dir=str(self.watch_dir),
            output_dir=str(self.output_dir),
            num_workers=1,  # Single worker for ordered processing
        )

        # Initialize worker pool manually
        from src.ingestion.worker_pool import WorkerPool

        watcher.worker_pool = WorkerPool(num_workers=1)
        await watcher.worker_pool.start()

        # Create test callback
        async def track_order(file_path: str):
            processing_order.append(file_path)
            await asyncio.sleep(0.05)

        # Submit tasks in reverse priority order
        await watcher.worker_pool.submit("batch.sql", track_order, Priority.BATCH)
        await watcher.worker_pool.submit("normal.sql", track_order, Priority.NORMAL)
        await watcher.worker_pool.submit("critical.sql", track_order, Priority.CRITICAL)

        # Wait for processing
        await asyncio.sleep(0.3)
        await watcher.worker_pool.task_queue.join()

        # Shutdown
        await watcher.worker_pool.shutdown()

        # Verify critical was processed first
        self.assertEqual(processing_order[0], "critical.sql")

    async def test_error_handling_in_parallel_processing(self):
        """Test that errors don't crash the worker pool."""
        # Create test files
        for i in range(5):
            sql_file = self.watch_dir / f"test_{i}.sql"
            sql_file.write_text("CREATE TABLE test (id INT);")

        # Mock the organizer to fail on some files
        with patch(
            "src.ingestion.parallel_file_watcher.HierarchicalOrganizer"
        ) as mock_org_class:
            mock_organizer = MagicMock()

            def side_effect(file_path):
                if "test_1" in file_path or "test_3" in file_path:
                    raise Exception("Simulated processing error")
                return {"tables": ["table.sql"]}

            mock_organizer.organize_file.side_effect = side_effect
            mock_org_class.return_value = mock_organizer

            watcher = ParallelFileWatcher(
                watch_dir=str(self.watch_dir),
                output_dir=str(self.output_dir),
                enable_batching=True,
                debounce_window=0.3,
                num_workers=2,
            )

            # Manually initialize components
            watcher.loop = asyncio.get_running_loop()

            from src.ingestion.worker_pool import WorkerPool

            watcher.worker_pool = WorkerPool(num_workers=2)
            await watcher.worker_pool.start()

            from src.ingestion.batch_processor import BatchProcessor

            watcher.batch_processor = BatchProcessor(
                process_callback=watcher._process_batch,
                debounce_window=0.3,
                enable_batching=True,
            )

            # Add files
            for i in range(5):
                await watcher.batch_processor.add_event(
                    str(self.watch_dir / f"test_{i}.sql")
                )

            # Wait for processing
            await asyncio.sleep(1.2)

            # Shutdown
            await watcher.batch_processor.shutdown()
            await watcher.worker_pool.shutdown()

            # Verify all files were attempted
            self.assertEqual(mock_organizer.organize_file.call_count, 5)

            # Verify statistics show failures
            stats = watcher.worker_pool.get_stats()
            self.assertEqual(stats["tasks_failed"], 2)
            self.assertEqual(stats["tasks_completed"], 3)

    async def test_batch_size_threshold_triggers_immediate_processing(self):
        """Test that reaching batch size threshold triggers immediate processing."""
        # Create test files
        for i in range(10):
            sql_file = self.watch_dir / f"test_{i}.sql"
            sql_file.write_text("CREATE TABLE test (id INT);")

        processed_batches = []

        # Mock the organizer
        with patch(
            "src.ingestion.parallel_file_watcher.HierarchicalOrganizer"
        ) as mock_org_class:
            mock_organizer = MagicMock()
            mock_organizer.organize_file.return_value = {"tables": ["table.sql"]}
            mock_org_class.return_value = mock_organizer

            watcher = ParallelFileWatcher(
                watch_dir=str(self.watch_dir),
                output_dir=str(self.output_dir),
                enable_batching=True,
                debounce_window=5.0,  # Long debounce
                batch_size_threshold=5,  # Trigger at 5 files
                num_workers=2,
            )

            # Manually initialize components
            watcher.loop = asyncio.get_running_loop()

            from src.ingestion.worker_pool import WorkerPool

            watcher.worker_pool = WorkerPool(num_workers=2)
            await watcher.worker_pool.start()

            from src.ingestion.batch_processor import BatchProcessor

            # Track batches
            original_process_batch = watcher._process_batch

            async def track_batches(file_paths):
                processed_batches.append(len(file_paths))
                await original_process_batch(file_paths)

            watcher.batch_processor = BatchProcessor(
                process_callback=track_batches,
                debounce_window=5.0,
                batch_size_threshold=5,
                enable_batching=True,
            )

            # Add 10 files (should trigger 2 batches of 5)
            for i in range(10):
                await watcher.batch_processor.add_event(
                    str(self.watch_dir / f"test_{i}.sql")
                )
                await asyncio.sleep(0.05)  # Small delay between adds

            # Wait for processing (but less than debounce window)
            await asyncio.sleep(1.0)

            # Shutdown
            await watcher.batch_processor.shutdown()
            await watcher.worker_pool.shutdown()

            # Should have processed 2 batches of 5
            self.assertEqual(len(processed_batches), 2)
            self.assertEqual(processed_batches[0], 5)
            self.assertEqual(processed_batches[1], 5)

    async def test_statistics_tracking(self):
        """Test that statistics are tracked correctly across components."""
        # Create test files
        for i in range(15):
            sql_file = self.watch_dir / f"test_{i}.sql"
            sql_file.write_text("CREATE TABLE test (id INT);")

        # Mock the organizer
        with patch(
            "src.ingestion.parallel_file_watcher.HierarchicalOrganizer"
        ) as mock_org_class:
            mock_organizer = MagicMock()
            mock_organizer.organize_file.return_value = {"tables": ["table.sql"]}
            mock_org_class.return_value = mock_organizer

            watcher = ParallelFileWatcher(
                watch_dir=str(self.watch_dir),
                output_dir=str(self.output_dir),
                enable_batching=True,
                debounce_window=0.3,
                num_workers=3,
            )

            # Manually initialize components
            watcher.loop = asyncio.get_running_loop()

            from src.ingestion.worker_pool import WorkerPool

            watcher.worker_pool = WorkerPool(num_workers=3, max_queue_size=50)
            await watcher.worker_pool.start()

            from src.ingestion.batch_processor import BatchProcessor

            watcher.batch_processor = BatchProcessor(
                process_callback=watcher._process_batch,
                debounce_window=0.3,
                enable_batching=True,
            )

            # Add files
            for i in range(15):
                await watcher.batch_processor.add_event(
                    str(self.watch_dir / f"test_{i}.sql")
                )

            # Wait for processing
            await asyncio.sleep(1.5)
            await watcher.worker_pool.task_queue.join()

            # Get statistics
            batch_stats = watcher.batch_processor.get_stats()
            worker_stats = watcher.worker_pool.get_stats()

            # Shutdown
            await watcher.batch_processor.shutdown()
            await watcher.worker_pool.shutdown()

            # Verify batch processor statistics
            self.assertEqual(batch_stats["events_received"], 15)
            self.assertGreater(batch_stats["batches_processed"], 0)

            # Verify worker pool statistics
            self.assertEqual(worker_stats["num_workers"], 3)
            self.assertEqual(worker_stats["tasks_completed"], 15)
            self.assertEqual(worker_stats["tasks_failed"], 0)
            self.assertEqual(worker_stats["success_rate_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
