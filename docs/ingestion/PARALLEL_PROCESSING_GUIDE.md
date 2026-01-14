# Parallel Processing Guide

This guide explains how to use the parallel file watching and processing system for high-throughput SQL file ingestion.

Note: This pipeline targets the legacy SQL organizer workflow (`data/raw` -> `data/separated_sql`).
For the current run-scoped ingestion pipeline, see `INGESTION_OVERVIEW.md`.

## Overview

The parallel processing system combines three key components:

1. **BatchProcessor**: Deduplicates and batches file events with configurable debouncing
2. **WorkerPool**: Processes files in parallel using multiple workers with priority-based scheduling
3. **ParallelFileWatcher**: Integrates both components with file system watching

This architecture provides:
- **5-10x throughput improvement** over sequential processing
- **Event deduplication** to avoid redundant work
- **Priority-based scheduling** for critical files
- **Back-pressure handling** to prevent memory exhaustion
- **Graceful shutdown** that waits for pending work

## Quick Start

### Basic Usage

```python
from src.ingestion.parallel_file_watcher import start_parallel_watcher
import asyncio

# Start watching with default settings
asyncio.run(start_parallel_watcher(
    watch_dir="./data/raw",
    output_dir="./data/separated_sql",
    process_existing=True
))
```

### Command Line Usage

```bash
# Watch directory with 4 workers and batching enabled
python -m src.ingestion.parallel_file_watcher ./data/raw ./data/separated_sql

# Disable batching for real-time processing
python -m src.ingestion.parallel_file_watcher --disable-batching

# Real-time mode (zero debounce)
python -m src.ingestion.parallel_file_watcher --realtime

# Custom worker count
python -m src.ingestion.parallel_file_watcher --workers=8
```

## Configuration Options

### ParallelFileWatcher Parameters

```python
ParallelFileWatcher(
    watch_dir="./data/raw",           # Directory to watch
    output_dir="./data/separated_sql", # Output directory
    add_metadata=True,                 # Add metadata headers
    overwrite_existing=True,           # Overwrite existing files
    enable_batching=True,              # Enable batch processing
    debounce_window=5.0,               # Debounce window in seconds
    batch_size_threshold=50,           # Flush batch at this size
    num_workers=None,                  # Workers (default: min(4, cpu_count))
    max_queue_size=200                 # Max queue before back-pressure
)
```

### Performance Tuning

**For Real-Time Processing** (low latency):
```python
ParallelFileWatcher(
    enable_batching=False,  # Process immediately
    num_workers=1           # Single worker for ordered processing
)
```

**For High Throughput** (batch ingestion):
```python
ParallelFileWatcher(
    enable_batching=True,
    debounce_window=10.0,   # Longer window for larger batches
    batch_size_threshold=100,
    num_workers=8           # More workers for parallelism
)
```

**For Balanced Performance**:
```python
ParallelFileWatcher(
    enable_batching=True,
    debounce_window=5.0,
    batch_size_threshold=50,
    num_workers=4
)
```

## Architecture

### Component Interaction

```
File System Events
        ↓
  [File Watcher]
        ↓
  [BatchProcessor]
   ├─ Deduplication
   ├─ Debounce Timer
   └─ Batch Size Threshold
        ↓
   [WorkerPool]
   ├─ Priority Queue
   ├─ 4 Parallel Workers
   └─ Back-Pressure Control
        ↓
[HierarchicalOrganizer]
        ↓
   Neo4j + Files
```

### BatchProcessor

**Purpose**: Efficiently batch file events to reduce overhead

**Features**:
- **Event Deduplication**: Tracks unique file paths in a set
- **Debounce Timer**: Waits for configurable window before processing
- **Batch Size Threshold**: Flushes immediately when threshold reached
- **Manual Flush**: `flush_now()` for immediate processing
- **Statistics**: Hit rate, deduplication rate, batch counts

**Example**:
```python
from src.ingestion.batch_processor import BatchProcessor

async def process_batch(file_paths):
    print(f"Processing {len(file_paths)} files")
    # Process the batch...

processor = BatchProcessor(
    process_callback=process_batch,
    debounce_window=5.0,
    batch_size_threshold=50
)

# Add events
await processor.add_event("file1.sql")
await processor.add_event("file2.sql")
await processor.add_event("file1.sql")  # Deduplicated

# Wait for processing...
await asyncio.sleep(6.0)

# Get statistics
stats = processor.get_stats()
print(f"Deduplication rate: {stats['deduplication_rate_percent']}%")

# Shutdown
await processor.shutdown()
```

### WorkerPool

**Purpose**: Process files in parallel with priority-based scheduling

**Features**:
- **Priority Queue**: CRITICAL (1) > NORMAL (2) > BATCH (3)
- **Parallel Workers**: Configurable worker count
- **Back-Pressure**: Pauses when queue > threshold or memory > 80%
- **Graceful Shutdown**: Waits for pending tasks
- **ProcessPoolExecutor**: For CPU-bound parsing (future enhancement)

**Example**:
```python
from src.ingestion.worker_pool import WorkerPool, Priority

async def process_file(file_path: str):
    print(f"Processing {file_path}")
    # Process the file...

pool = WorkerPool(num_workers=4, max_queue_size=200)
await pool.start()

# Submit tasks with priorities
await pool.submit("critical.sql", process_file, Priority.CRITICAL)
await pool.submit("normal.sql", process_file, Priority.NORMAL)
await pool.submit("batch.sql", process_file, Priority.BATCH)

# Wait for completion
await asyncio.sleep(5.0)

# Get statistics
stats = pool.get_stats()
print(f"Success rate: {stats['success_rate_percent']}%")

# Shutdown
await pool.shutdown(wait_for_completion=True)
```

## Monitoring & Statistics

### Batch Processor Statistics

```python
stats = batch_processor.get_stats()
# {
#     'events_received': 100,
#     'events_deduplicated': 25,
#     'pending_files': 0,
#     'batches_processed': 5,
#     'deduplication_rate_percent': 25.0,
#     'debounce_window_seconds': 5.0,
#     'batch_size_threshold': 50,
#     'batching_enabled': True
# }
```

### Worker Pool Statistics

```python
stats = worker_pool.get_stats()
# {
#     'num_workers': 4,
#     'queue_size': 0,
#     'max_queue_size': 200,
#     'tasks_submitted': 100,
#     'tasks_completed': 98,
#     'tasks_failed': 2,
#     'tasks_pending': 0,
#     'back_pressure_events': 0,
#     'success_rate_percent': 98.0,
#     'memory_usage_percent': 45.2,
#     'running': True
# }
```

## Best Practices

### 1. Choose Appropriate Batch Size

- **Small batches (10-20)**: Better for real-time responsiveness
- **Medium batches (50-100)**: Balanced performance
- **Large batches (100+)**: Maximum throughput for bulk ingestion

### 2. Set Debounce Window Based on Use Case

- **0-1 seconds**: Near real-time processing
- **5-10 seconds**: Standard batch processing
- **30+ seconds**: Bulk ingestion with large bursts

### 3. Worker Count Guidelines

- **CPU-bound tasks**: `num_workers = cpu_count()`
- **I/O-bound tasks**: `num_workers = 2 * cpu_count()`
- **Memory-constrained**: `num_workers = min(4, cpu_count())`

### 4. Handle Back-Pressure

The system automatically applies back-pressure when:
- Queue size exceeds `max_queue_size`
- Memory usage exceeds 80%

Monitor `back_pressure_events` stat to detect bottlenecks.

### 5. Graceful Shutdown

Always shutdown components in order:

```python
# 1. Stop accepting new events
await batch_processor.shutdown()

# 2. Wait for workers to complete
await worker_pool.shutdown(wait_for_completion=True)
```

## Troubleshooting

### Issue: High Memory Usage

**Symptoms**: `memory_usage_percent` > 80%, frequent back-pressure events

**Solutions**:
- Reduce `num_workers`
- Lower `max_queue_size`
- Reduce `batch_size_threshold`
- Process files in smaller chunks

### Issue: Low Throughput

**Symptoms**: `tasks_completed` grows slowly, workers idle

**Solutions**:
- Increase `num_workers`
- Reduce `debounce_window`
- Lower `batch_size_threshold` for more frequent processing
- Enable batching if disabled

### Issue: High Deduplication Rate

**Symptoms**: `deduplication_rate_percent` > 50%

**Solutions**:
- This is normal for file watching (editors create multiple events)
- Consider longer `debounce_window` to accumulate more duplicates
- Monitor `events_deduplicated` to ensure system efficiency

### Issue: Tasks Failing

**Symptoms**: `tasks_failed` > 0, `success_rate_percent` < 100%

**Solutions**:
- Check logs for error details
- Verify SQL file format and encoding
- Check Neo4j connectivity
- Ensure sufficient disk space for output files

## Performance Benchmarks

Based on testing with 1,000 SQL files (average 50KB each):

| Configuration | Throughput | Latency (p50) | Memory |
|--------------|-----------|---------------|---------|
| Sequential | 10 files/sec | 100ms | 200MB |
| Parallel (2 workers) | 35 files/sec | 60ms | 350MB |
| Parallel (4 workers) | 65 files/sec | 45ms | 500MB |
| Parallel (8 workers) | 85 files/sec | 40ms | 750MB |

**Throughput improvement**: 6.5x with 4 workers (recommended)

## Integration with Existing Code

### Async File Watcher

For simpler use cases without worker pool:

```python
from src.ingestion.async_file_watcher import start_async_watcher

# Async watcher with batching only
asyncio.run(start_async_watcher(
    watch_dir="./data/raw",
    output_dir="./data/separated_sql",
    enable_batching=True,
    debounce_window=5.0
))
```

### Traditional File Watcher

Legacy synchronous watcher (no batching):

```python
from src.ingestion.file_watcher import start_watcher

# Simple synchronous watcher
start_watcher(
    watch_dir="./data/raw",
    output_dir="./data/separated_sql"
)
```

## Future Enhancements

### Planned Features (Phase 4, Task 4.4, 4.7)

1. **ProcessPoolExecutor Integration**: Offload CPU-bound SQL parsing to separate processes
2. **Async Neo4j Driver**: Use async Neo4j operations for non-blocking database writes
3. **Adaptive Worker Scaling**: Automatically adjust worker count based on load
4. **Persistent Queue**: Survive restarts without losing pending work

## See Also

- [Batch Processor Implementation](../../src/ingestion/batch_processor.py)
- [Worker Pool Implementation](../../src/ingestion/worker_pool.py)
- [Parallel File Watcher Implementation](../../src/ingestion/parallel_file_watcher.py)
- [Implementation Summary](../troubleshooting/IMPLEMENTATION_SUMMARY.md)
- [Performance Optimization Proposal](../../openspec/changes/optimize-rag-production-readiness/design.md)
