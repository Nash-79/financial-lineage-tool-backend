"""
File Watcher - Monitors data/raw/ folder for new SQL files and automatically processes them.

This watcher monitors the data/raw/ directory for:
- New .sql files added
- Modified .sql files
- Automatically triggers hierarchical organization

Usage:
    python -m src.ingestion.file_watcher

    Or programmatically:
    from src.ingestion.file_watcher import SQLFileWatcher
    watcher = SQLFileWatcher()
    watcher.start()
"""

import time
from pathlib import Path
from typing import Set
import logging

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("[ERROR] watchdog library not installed. Install with: pip install watchdog")
    raise

from .hierarchical_organizer import HierarchicalOrganizer


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SQLFileHandler(FileSystemEventHandler):
    """
    Handler for SQL file system events.

    Processes .sql files when they are created or modified.
    """

    def __init__(self, organizer: HierarchicalOrganizer, debounce_seconds: float = 2.0):
        """
        Initialize SQL file handler.

        Args:
            organizer: HierarchicalOrganizer instance
            debounce_seconds: Seconds to wait before processing (avoid duplicate events)
        """
        self.organizer = organizer
        self.debounce_seconds = debounce_seconds
        self.processing_files: Set[str] = set()
        self.last_processed: dict = {}

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith(".sql"):
            logger.info(f"[NEW FILE] Detected: {event.src_path}")
            self._process_file(event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith(".sql"):
            # Check if we recently processed this file (debounce)
            if self._should_process(event.src_path):
                logger.info(f"[MODIFIED] Detected: {event.src_path}")
                self._process_file(event.src_path)

    def _should_process(self, file_path: str) -> bool:
        """
        Check if file should be processed (debouncing).

        Args:
            file_path: Path to file

        Returns:
            True if file should be processed
        """
        now = time.time()
        last_time = self.last_processed.get(file_path, 0)

        if now - last_time < self.debounce_seconds:
            return False

        return True

    def _process_file(self, file_path: str):
        """
        Process SQL file through hierarchical organizer.

        Args:
            file_path: Path to SQL file
        """
        # Avoid duplicate processing
        if file_path in self.processing_files:
            logger.debug(f"[SKIP] Already processing: {file_path}")
            return

        try:
            self.processing_files.add(file_path)
            self.last_processed[file_path] = time.time()

            logger.info("=" * 70)
            logger.info(f"[PROCESSING] {Path(file_path).name}")
            logger.info("=" * 70)

            # Process using hierarchical organizer
            results = self.organizer.organize_file(file_path)

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
        finally:
            self.processing_files.discard(file_path)


class SQLFileWatcher:
    """
    File watcher for automatic SQL file processing.

    Monitors data/raw/ directory and automatically processes new/modified SQL files.
    """

    def __init__(
        self,
        watch_dir: str = "./data/raw",
        output_dir: str = "./data/separated_sql",
        add_metadata: bool = True,
        overwrite_existing: bool = True,
        debounce_seconds: float = 2.0,
    ):
        """
        Initialize file watcher.

        Args:
            watch_dir: Directory to watch for SQL files
            output_dir: Output directory for organized files
            add_metadata: Add metadata headers to files
            overwrite_existing: Overwrite existing files
            debounce_seconds: Seconds to wait before processing (avoid duplicates)
        """
        self.watch_dir = Path(watch_dir)
        self.output_dir = Path(output_dir)

        # Create directories if they don't exist
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize hierarchical organizer
        self.organizer = HierarchicalOrganizer(
            output_base_dir=str(self.output_dir),
            add_metadata_header=add_metadata,
            overwrite_existing=overwrite_existing,
        )

        # Initialize file handler
        self.event_handler = SQLFileHandler(
            organizer=self.organizer, debounce_seconds=debounce_seconds
        )

        # Initialize observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.watch_dir), recursive=False)

        logger.info("[INIT] File watcher initialized")
        logger.info(f"[INIT] Watching: {self.watch_dir.absolute()}")
        logger.info(f"[INIT] Output: {self.output_dir.absolute()}")

    def start(self, process_existing: bool = True):
        """
        Start watching for file changes.

        Args:
            process_existing: Process existing SQL files in directory
        """
        logger.info("=" * 70)
        logger.info("=== SQL FILE WATCHER STARTED ===")
        logger.info("=" * 70)

        # Process existing files first
        if process_existing:
            self._process_existing_files()

        # Start observer
        self.observer.start()

        logger.info(f"[OK] Watching for changes in: {self.watch_dir}")
        logger.info("[INFO] Press Ctrl+C to stop")
        logger.info("=" * 70)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop watching for file changes."""
        logger.info("\n[INFO] Stopping file watcher...")
        self.observer.stop()
        self.observer.join()

        # Print summary
        self.organizer.print_summary()

        logger.info("[OK] File watcher stopped")

    def _process_existing_files(self):
        """Process existing SQL files in watch directory."""
        sql_files = list(self.watch_dir.glob("*.sql"))

        if not sql_files:
            logger.info("[INFO] No existing SQL files found")
            return

        logger.info(f"[INFO] Found {len(sql_files)} existing SQL file(s)")
        logger.info("[INFO] Processing existing files...")

        for sql_file in sql_files:
            logger.info(f"[PROCESSING] {sql_file.name}")
            try:
                results = self.organizer.organize_file(str(sql_file))
                if results:
                    logger.info(f"[OK] Processed: {sql_file.name}")
                else:
                    logger.warning(f"[WARN] No objects in: {sql_file.name}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to process {sql_file.name}: {e}")

        logger.info("[OK] Existing files processed")
        logger.info("=" * 70)


def start_watcher(
    watch_dir: str = "./data/raw",
    output_dir: str = "./data/separated_sql",
    process_existing: bool = True,
):
    """
    Convenience function to start SQL file watcher.

    Args:
        watch_dir: Directory to watch
        output_dir: Output directory
        process_existing: Process existing files on startup
    """
    watcher = SQLFileWatcher(watch_dir=watch_dir, output_dir=output_dir)

    watcher.start(process_existing=process_existing)


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    watch_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/raw"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./data/separated_sql"

    print("SQL File Watcher")
    print("=" * 70)
    print(f"Watch Directory:  {Path(watch_dir).absolute()}")
    print(f"Output Directory: {Path(output_dir).absolute()}")
    print("=" * 70)
    print()

    start_watcher(watch_dir, output_dir)
