"""
Async File Watcher - Enhanced file watcher with batch processing support.

This module provides an async-based file watcher that integrates with BatchProcessor
for efficient event handling and processing.
"""

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional, List
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("[ERROR] watchdog library not installed. Install with: pip install watchdog")
    raise

from .batch_processor import BatchProcessor
from .hierarchical_organizer import HierarchicalOrganizer

logger = logging.getLogger(__name__)


class AsyncSQLFileHandler(FileSystemEventHandler):
    """
    Async handler for SQL file system events with batch processing.
    """

    def __init__(
        self,
        batch_processor: BatchProcessor,
        organizer: HierarchicalOrganizer,
        enable_batching: bool = True,
    ):
        """
        Initialize async SQL file handler.

        Args:
            batch_processor: BatchProcessor instance
            organizer: HierarchicalOrganizer instance
            enable_batching: Enable batch processing (default: True)
        """
        self.batch_processor = batch_processor
        self.organizer = organizer
        self.enable_batching = enable_batching
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the asyncio event loop."""
        self.event_loop = loop

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith(".sql"):
            logger.info(f"[NEW FILE] Detected: {event.src_path}")
            self._queue_file(event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith(".sql"):
            logger.info(f"[MODIFIED] Detected: {event.src_path}")
            self._queue_file(event.src_path)

    def _queue_file(self, file_path: str):
        """
        Queue file for processing.

        Args:
            file_path: Path to file
        """
        if self.event_loop and not self.event_loop.is_closed():
            # Schedule file processing in the event loop
            asyncio.run_coroutine_threadsafe(
                self.batch_processor.add_event(file_path), self.event_loop
            )


class AsyncSQLFileWatcher:
    """
    Async file watcher for SQL files with batch processing.

    Features:
    - Batch processing with configurable debounce
    - Async/await architecture
    - Graceful shutdown
    - Statistics tracking
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
    ):
        """
        Initialize async file watcher.

        Args:
            watch_dir: Directory to watch for SQL files
            output_dir: Output directory for organized files
            add_metadata: Add metadata headers to files
            overwrite_existing: Overwrite existing files
            enable_batching: Enable batch processing (default: True)
            debounce_window: Debounce window in seconds (default: 5.0)
            batch_size_threshold: Batch size threshold (default: 50)
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

        # Initialize batch processor
        self.batch_processor: Optional[BatchProcessor] = None
        self.debounce_window = debounce_window
        self.batch_size_threshold = batch_size_threshold

        # Watchdog observer
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[AsyncSQLFileHandler] = None

        # Event loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_event = asyncio.Event()

        logger.info("[INIT] Async file watcher initialized")
        logger.info(f"[INIT] Watching: {self.watch_dir.absolute()}")
        logger.info(f"[INIT] Output: {self.output_dir.absolute()}")
        logger.info(f"[INIT] Batching: {'Enabled' if enable_batching else 'Disabled'}")

    async def _process_file(self, file_path: str):
        """
        Process SQL file through hierarchical organizer.

        Args:
            file_path: Path to SQL file
        """
        try:
            logger.info("=" * 70)
            logger.info(f"[PROCESSING] {Path(file_path).name}")
            logger.info("=" * 70)

            # Process using hierarchical organizer (synchronous)
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self.organizer.organize_file, file_path
            )

            if results:
                logger.info(f"[OK] Successfully processed: {Path(file_path).name}")
                logger.info(
                    f"[OK] Created {sum(len(v) for v in results.values())} files"
                )
            else:
                logger.warning(f"[WARN] No objects found in: {Path(file_path).name}")

            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"[ERROR] Failed to process {file_path}: {e}", exc_info=True)

    async def _process_batch(self, file_paths: List[str]):
        """
        Process batch of file paths.

        Args:
            file_paths: List of file paths to process
        """
        logger.info(f"[BATCH] Processing {len(file_paths)} files")

        # Process each file
        for file_path in file_paths:
            await self._process_file(file_path)

        logger.info(f"[BATCH] Completed processing {len(file_paths)} files")

    async def start(self, process_existing: bool = True):
        """
        Start watching for file changes.

        Args:
            process_existing: Process existing SQL files in directory
        """
        logger.info("=" * 70)
        logger.info("=== ASYNC SQL FILE WATCHER STARTED ===")
        logger.info("=" * 70)

        # Get event loop
        self.loop = asyncio.get_running_loop()

        # Initialize batch processor
        self.batch_processor = BatchProcessor(
            process_callback=self._process_batch,
            debounce_window=self.debounce_window,
            batch_size_threshold=self.batch_size_threshold,
            enable_batching=self.enable_batching,
        )

        # Initialize event handler
        self.event_handler = AsyncSQLFileHandler(
            batch_processor=self.batch_processor,
            organizer=self.organizer,
            enable_batching=self.enable_batching,
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

        logger.info(f"[OK] Watching for changes in: {self.watch_dir}")
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

        logger.info("\n[INFO] Stopping file watcher...")

        # Stop observer
        if self.observer:
            self.observer.stop()
            self.observer.join()

        # Shutdown batch processor
        if self.batch_processor:
            await self.batch_processor.shutdown()

        # Print statistics
        if self.batch_processor:
            logger.info("\nBatch Processor Statistics:")
            stats = self.batch_processor.get_stats()
            for key, value in stats.items():
                logger.info(f"  {key}: {value}")

        # Print organizer summary
        self.organizer.print_summary()

        logger.info("[OK] File watcher stopped")
        self._shutdown_event.set()

    async def _process_existing_files(self):
        """Process existing SQL files in watch directory."""
        sql_files = list(self.watch_dir.glob("*.sql"))

        if not sql_files:
            logger.info("[INFO] No existing SQL files found")
            return

        logger.info(f"[INFO] Found {len(sql_files)} existing SQL file(s)")
        logger.info("[INFO] Processing existing files...")

        # Add files to batch processor
        for sql_file in sql_files:
            await self.batch_processor.add_event(str(sql_file))

        # Wait for processing to complete
        await asyncio.sleep(self.debounce_window + 0.5)

        logger.info("[OK] Existing files queued for processing")
        logger.info("=" * 70)


async def start_async_watcher(
    watch_dir: str = "./data/raw",
    output_dir: str = "./data/separated_sql",
    process_existing: bool = True,
    enable_batching: bool = True,
    debounce_window: float = 5.0,
    batch_size_threshold: int = 50,
):
    """
    Convenience function to start async SQL file watcher.

    Args:
        watch_dir: Directory to watch
        output_dir: Output directory
        process_existing: Process existing files on startup
        enable_batching: Enable batch processing
        debounce_window: Debounce window in seconds
        batch_size_threshold: Batch size threshold
    """
    watcher = AsyncSQLFileWatcher(
        watch_dir=watch_dir,
        output_dir=output_dir,
        enable_batching=enable_batching,
        debounce_window=debounce_window,
        batch_size_threshold=batch_size_threshold,
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

    # Set debounce based on mode
    debounce = 0.0 if realtime else 5.0

    print("Async SQL File Watcher")
    print("=" * 70)
    print(f"Watch Directory:  {Path(watch_dir).absolute()}")
    print(f"Output Directory: {Path(output_dir).absolute()}")
    print(f"Batching: {'Enabled' if enable_batching else 'Disabled'}")
    print(f"Debounce: {debounce}s")
    print("=" * 70)
    print()

    # Run watcher
    asyncio.run(
        start_async_watcher(
            watch_dir=watch_dir,
            output_dir=output_dir,
            enable_batching=enable_batching,
            debounce_window=debounce,
        )
    )
