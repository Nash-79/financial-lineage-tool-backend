"""
Parallel File Watcher - File watcher with batch processing and parallel execution.

This module combines BatchProcessor and WorkerPool for maximum throughput:
- Batch file events with debouncing
- Parallel SQL parsing using worker pool
- Priority-based task processing
"""

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional, List

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("[ERROR] watchdog library not installed. Install with: pip install watchdog")
    raise

from .batch_processor import BatchProcessor
from .worker_pool import WorkerPool, Priority
from .hierarchical_organizer import HierarchicalOrganizer

logger = logging.getLogger(__name__)


class ParallelSQLFileHandler(FileSystemEventHandler):
    """
    Handler for SQL file system events with batch and parallel processing.
    """

    def __init__(self, batch_processor: BatchProcessor, enable_batching: bool = True):
        """
        Initialize parallel SQL file handler.

        Args:
            batch_processor: BatchProcessor instance
            enable_batching: Enable batch processing (default: True)
        """
        self.batch_processor = batch_processor
        self.enable_batching = enable_batching
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the asyncio event loop."""
        self.event_loop = loop

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith(".sql"):
            logger.info(f"[NEW FILE] Detected: {event.src_path}")
            self._queue_file(event.src_path, Priority.NORMAL)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith(".sql"):
            logger.info(f"[MODIFIED] Detected: {event.src_path}")
            self._queue_file(event.src_path, Priority.NORMAL)

    def _queue_file(self, file_path: str, priority: Priority = Priority.NORMAL):
        """
        Queue file for processing.

        Args:
            file_path: Path to file
            priority: Task priority
        """
        if self.event_loop and not self.event_loop.is_closed():
            # Schedule file processing in the event loop
            asyncio.run_coroutine_threadsafe(
                self.batch_processor.add_event(file_path), self.event_loop
            )


class ParallelFileWatcher:
    """
    Parallel file watcher for SQL files with batch processing and worker pool.

    Combines:
    - BatchProcessor for event deduplication and debouncing
    - WorkerPool for parallel SQL parsing
    - Priority-based task execution
    """

    def __init__(
        self,
        watch_dir: str = "./data/raw",
        output_dir: str = "./data/separated_sql",
        add_metadata: bool = True,
        overwrite_existing: bool = True,
        enable_batching: bool = True,
        debounce_window: float = 5.0,
        batch_size_threshold: int = 50,
        num_workers: int = None,
        max_queue_size: int = 200,
    ):
        """
        Initialize parallel file watcher.

        Args:
            watch_dir: Directory to watch for SQL files
            output_dir: Output directory for organized files
            add_metadata: Add metadata headers to files
            overwrite_existing: Overwrite existing files
            enable_batching: Enable batch processing (default: True)
            debounce_window: Debounce window in seconds (default: 5.0)
            batch_size_threshold: Batch size threshold (default: 50)
            num_workers: Number of parallel workers (default: min(4, cpu_count()))
            max_queue_size: Max worker queue size (default: 200)
        """
        self.watch_dir = Path(watch_dir)
        self.output_dir = Path(output_dir)
        self.enable_batching = enable_batching

        # Create directories
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize organizer
        self.organizer = HierarchicalOrganizer(
            output_base_dir=str(self.output_dir),
            add_metadata_header=add_metadata,
            overwrite_existing=overwrite_existing,
        )

        # Worker pool configuration
        self.num_workers = num_workers or min(4, os.cpu_count() or 1)
        self.max_queue_size = max_queue_size

        # Components
        self.batch_processor: Optional[BatchProcessor] = None
        self.worker_pool: Optional[WorkerPool] = None
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[ParallelSQLFileHandler] = None

        # Configuration
        self.debounce_window = debounce_window
        self.batch_size_threshold = batch_size_threshold

        # Event loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_event = asyncio.Event()

        logger.info("[INIT] Parallel file watcher initialized")
        logger.info(f"[INIT] Watching: {self.watch_dir.absolute()}")
        logger.info(f"[INIT] Output: {self.output_dir.absolute()}")
        logger.info(f"[INIT] Workers: {self.num_workers}")
        logger.info(f"[INIT] Batching: {'Enabled' if enable_batching else 'Disabled'}")

    async def _process_file(self, file_path: str):
        """
        Process SQL file through hierarchical organizer.

        Uses ProcessPoolExecutor for CPU-bound SQL parsing to avoid blocking
        the asyncio event loop with regex operations.

        Args:
            file_path: Path to SQL file
        """
        logger.debug(f"[WORKER] Processing: {Path(file_path).name}")

        # Use ProcessPoolExecutor from worker pool for CPU-bound parsing
        # This offloads regex-intensive SQL parsing to a separate process
        loop = asyncio.get_event_loop()

        # Get executor from worker pool (ProcessPoolExecutor for true parallelism)
        executor = (
            self.worker_pool.executor
            if self.worker_pool and self.worker_pool.executor
            else None
        )

        results = await loop.run_in_executor(
            executor,  # Use ProcessPoolExecutor instead of default ThreadPoolExecutor
            self.organizer.organize_file,
            file_path,
        )

        if results:
            logger.info(
                f"[OK] Processed {Path(file_path).name}: "
                f"{sum(len(v) for v in results.values())} files created"
            )
        else:
            logger.warning(f"[WARN] No objects found in: {Path(file_path).name}")

    async def _process_batch(self, file_paths: List[str]):
        """
        Process batch of file paths using worker pool.

        Args:
            file_paths: List of file paths to process
        """
        logger.info(f"[BATCH] Processing {len(file_paths)} files in parallel")

        # Submit all files to worker pool for parallel processing
        tasks = []
        for file_path in file_paths:
            # Submit to worker pool with normal priority
            task = self.worker_pool.submit(
                file_path, self._process_file, Priority.NORMAL
            )
            tasks.append(task)

        # Wait for all submissions
        await asyncio.gather(*tasks)

        logger.info(f"[BATCH] Submitted {len(file_paths)} files to worker pool")

    async def start(self, process_existing: bool = True):
        """
        Start watching for file changes.

        Args:
            process_existing: Process existing SQL files in directory
        """
        logger.info("=" * 70)
        logger.info("=== PARALLEL SQL FILE WATCHER STARTED ===")
        logger.info("=" * 70)

        # Get event loop
        self.loop = asyncio.get_running_loop()

        # Initialize worker pool
        self.worker_pool = WorkerPool(
            num_workers=self.num_workers,
            max_queue_size=self.max_queue_size,
            enable_back_pressure=True,
        )
        await self.worker_pool.start()

        # Initialize batch processor
        self.batch_processor = BatchProcessor(
            process_callback=self._process_batch,
            debounce_window=self.debounce_window,
            batch_size_threshold=self.batch_size_threshold,
            enable_batching=self.enable_batching,
        )

        # Initialize event handler
        self.event_handler = ParallelSQLFileHandler(
            batch_processor=self.batch_processor, enable_batching=self.enable_batching
        )
        self.event_handler.set_event_loop(self.loop)

        # Initialize observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.watch_dir), recursive=False)

        # Process existing files
        if process_existing:
            await self._process_existing_files()

        # Start observer
        self.observer.start()

        logger.info(f"[OK] Watching: {self.watch_dir}")
        logger.info(f"[OK] Workers: {self.num_workers} parallel workers running")
        logger.info("[INFO] Press Ctrl+C to stop")
        logger.info("=" * 70)

        # Setup signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            self.loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Wait for shutdown
        await self._shutdown_event.wait()

    async def stop(self):
        """Stop watching for file changes."""
        if self._shutdown_event.is_set():
            return

        logger.info("\n[INFO] Stopping parallel file watcher...")

        # Stop observer
        if self.observer:
            self.observer.stop()
            self.observer.join()

        # Shutdown batch processor
        if self.batch_processor:
            logger.info("[INFO] Flushing remaining batches...")
            await self.batch_processor.shutdown()

        # Shutdown worker pool
        if self.worker_pool:
            logger.info("[INFO] Waiting for workers to complete...")
            await self.worker_pool.shutdown(wait_for_completion=True)

        # Print statistics
        logger.info("\n" + "=" * 70)
        logger.info("STATISTICS")
        logger.info("=" * 70)

        if self.batch_processor:
            logger.info("\nBatch Processor:")
            stats = self.batch_processor.get_stats()
            for key, value in stats.items():
                logger.info(f"  {key}: {value}")

        if self.worker_pool:
            logger.info("\nWorker Pool:")
            stats = self.worker_pool.get_stats()
            for key, value in stats.items():
                logger.info(f"  {key}: {value}")

        # Print organizer summary
        logger.info("\nFile Organization:")
        self.organizer.print_summary()

        logger.info("=" * 70)
        logger.info("[OK] Parallel file watcher stopped")
        self._shutdown_event.set()

    async def _process_existing_files(self):
        """Process existing SQL files in watch directory."""
        sql_files = list(self.watch_dir.glob("*.sql"))

        if not sql_files:
            logger.info("[INFO] No existing SQL files found")
            return

        logger.info(f"[INFO] Found {len(sql_files)} existing SQL file(s)")
        logger.info("[INFO] Processing existing files in parallel...")

        # Add files to batch processor
        for sql_file in sql_files:
            await self.batch_processor.add_event(str(sql_file))

        # Wait for processing to complete
        await asyncio.sleep(self.debounce_window + 0.5)

        logger.info("[OK] Existing files queued for processing")
        logger.info("=" * 70)


async def start_parallel_watcher(
    watch_dir: str = "./data/raw",
    output_dir: str = "./data/separated_sql",
    process_existing: bool = True,
    enable_batching: bool = True,
    debounce_window: float = 5.0,
    batch_size_threshold: int = 50,
    num_workers: int = None,
):
    """
    Convenience function to start parallel SQL file watcher.

    Args:
        watch_dir: Directory to watch
        output_dir: Output directory
        process_existing: Process existing files on startup
        enable_batching: Enable batch processing
        debounce_window: Debounce window in seconds
        batch_size_threshold: Batch size threshold
        num_workers: Number of parallel workers
    """
    watcher = ParallelFileWatcher(
        watch_dir=watch_dir,
        output_dir=output_dir,
        enable_batching=enable_batching,
        debounce_window=debounce_window,
        batch_size_threshold=batch_size_threshold,
        num_workers=num_workers,
    )

    await watcher.start(process_existing=process_existing)


if __name__ == "__main__":
    import sys
    import os

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Check for cache management commands
    if "--clear-cache" in sys.argv:
        from .parse_cache import ParseCache

        cache_path = os.environ.get("PARSE_CACHE_PATH", "data/.cache/parse_cache.db")
        print(f"Clearing parse cache: {cache_path}")

        cache = ParseCache(cache_path=cache_path)
        cache.clear()

        print("[OK] Cache cleared successfully")
        sys.exit(0)

    if "--cache-stats" in sys.argv:
        from .parse_cache import ParseCache
        from datetime import datetime

        cache_path = os.environ.get("PARSE_CACHE_PATH", "data/.cache/parse_cache.db")
        print(f"Parse Cache Statistics: {cache_path}")
        print("=" * 70)

        cache = ParseCache(cache_path=cache_path)
        stats = cache.get_stats()

        print(f"Total Entries:       {stats['entry_count']} / {stats['max_entries']}")
        print(f"Cache Hits:          {stats['hits']}")
        print(f"Cache Misses:        {stats['misses']}")
        print(f"Hit Rate:            {stats['hit_rate_percent']:.2f}%")
        print(f"Database Size:       {stats['cache_size_mb']:.2f} MB")

        if stats["oldest_entry"]:
            try:
                oldest = datetime.fromisoformat(stats["oldest_entry"])
                age_days = (datetime.now() - oldest).days
                print(f"Oldest Entry:        {age_days} days ago")
            except:
                print(f"Oldest Entry:        {stats['oldest_entry']}")
        else:
            print("Oldest Entry:        N/A")

        print(f"TTL:                 {stats['ttl_days']} days")
        print("=" * 70)

        sys.exit(0)

    # Parse command line arguments
    watch_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/raw"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./data/separated_sql"

    # Check for flags
    enable_batching = "--disable-batching" not in sys.argv
    realtime = "--realtime" in sys.argv

    # Parse worker count
    num_workers = None
    for arg in sys.argv:
        if arg.startswith("--workers="):
            try:
                num_workers = int(arg.split("=")[1])
            except ValueError:
                print(f"[WARN] Invalid workers value: {arg}")

    # Set debounce based on mode
    debounce = 0.0 if realtime else 5.0

    print("Parallel SQL File Watcher")
    print("=" * 70)
    print(f"Watch Directory:  {Path(watch_dir).absolute()}")
    print(f"Output Directory: {Path(output_dir).absolute()}")
    print(f"Batching: {'Enabled' if enable_batching else 'Disabled'}")
    print(f"Debounce: {debounce}s")
    print(f"Workers: {num_workers or 'auto (min(4, cpu_count()))'}")
    print("=" * 70)
    print()

    # Run watcher
    asyncio.run(
        start_parallel_watcher(
            watch_dir=watch_dir,
            output_dir=output_dir,
            enable_batching=enable_batching,
            debounce_window=debounce,
            num_workers=num_workers,
        )
    )
