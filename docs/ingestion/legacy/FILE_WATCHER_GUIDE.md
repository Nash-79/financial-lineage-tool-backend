# SQL File Watcher - Automatic Processing Guide

Note: This guide covers the legacy organizer workflow (`data/raw` -> `data/separated_sql`).
For the run-scoped ingestion pipeline, see `../INGESTION_OVERVIEW.md`.

## Overview

The **SQL File Watcher** automatically monitors the `data/raw/` directory and processes SQL files as soon as they are added or modified. This enables seamless integration into your workflow - simply drop a SQL file into the watched folder and it will be automatically organized hierarchically.

## Key Features

### 1. Automatic Detection
- Monitors `data/raw/` directory in real-time
- Detects new SQL files immediately
- Detects modifications to existing SQL files
- No manual intervention required

### 2. Intelligent Processing
- **Debouncing**: Avoids duplicate processing from rapid file changes
- **Error Handling**: Continues monitoring even if one file fails
- **Logging**: Comprehensive logging of all processing activities
- **Statistics**: Tracks objects processed, files created, errors encountered

### 3. Hierarchical Organization
- Uses the same hierarchical organizer
- SQL Server comment pattern detection
- Parent-child relationship preservation
- Metadata headers on all files

### 4. Startup Options
- **Process Existing Files**: Optionally process all existing SQL files on startup
- **Configurable Paths**: Customize watch and output directories
- **Configurable Debouncing**: Adjust delay between processing events

## Quick Start

### 1. Install Dependencies

```bash
pip install watchdog>=3.0.0
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

### 2. Start the Watcher

```bash
cd financial-lineage-tool
python examples/start_file_watcher.py
```

You'll see:

```
===================================================================
SQL FILE WATCHER - Automatic SQL File Processing
===================================================================

This watcher will:
1. Process all existing SQL files in data/raw/
2. Watch for new SQL files
3. Watch for modifications to existing files
4. Automatically organize files hierarchically

To test:
- Copy a .sql file to data/raw/
- Modify an existing .sql file in data/raw/
- Watch the automatic processing

Press Ctrl+C to stop
===================================================================

[INIT] File watcher initialized
[INIT] Watching: C:\path\to\data\raw
[INIT] Output: C:\path\to\data\separated_sql

=======================================================================
[INFO] Found 1 existing SQL file(s)
[INFO] Processing existing files...
[PROCESSING] AdventureWorksLT-All.sql
[OK] Processed: AdventureWorksLT-All.sql
[OK] Existing files processed
=======================================================================

[OK] Watching for changes in: C:\path\to\data\raw
[INFO] Press Ctrl+C to stop
=======================================================================
```

### 3. Add a SQL File

Simply copy a SQL file to `data/raw/`:

```bash
cp /path/to/your/database.sql data/raw/
```

The watcher will immediately detect and process it:

```
[NEW FILE] Detected: data/raw/database.sql
=======================================================================
[PROCESSING] database.sql
=======================================================================

Processing: data/raw\database.sql
Found 25 object(s)

  [OK] Table: Product -> tables/Product/Product.sql
    [OK] Index: PK_Product_ProductID
    [OK] Index: IX_Product_Name
  [OK] View: vProductSummary -> views/vProductSummary/vProductSummary.sql
  ...

[OK] Successfully processed: database.sql
[OK] Created 25 files
=======================================================================
```

### 4. Stop the Watcher

Press `Ctrl+C` to stop:

```
[INFO] Stopping file watcher...

=======================================================================
=== HIERARCHICAL ORGANIZATION SUMMARY ===
=======================================================================
Files Processed:          2
Objects Separated:        71
Tables with Constraints:  14
Indexed Views:            1

By Object Type:
  Table                 14
  View                   4
  UserDefinedFunction    3
  StoredProcedure       15
  Index                 10
  ...

[OK] Output Directory: data/separated_sql
=======================================================================

[OK] File watcher stopped
```

## Usage Patterns

### Pattern 1: Continuous Monitoring (Recommended)

Start the watcher and leave it running:

```bash
python examples/start_file_watcher.py
```

Then simply add SQL files to `data/raw/` whenever you need them processed.

**Best for**:
- Development workflows
- Continuous integration pipelines
- Production environments with regular SQL updates

### Pattern 2: One-Time Batch Processing

Start the watcher, let it process existing files, then stop:

```bash
# Add all SQL files to data/raw/ first
cp *.sql data/raw/

# Start watcher (processes existing files)
python examples/start_file_watcher.py

# Press Ctrl+C immediately after processing completes
```

**Best for**:
- Initial setup
- Batch processing of multiple files
- One-off migrations

### Pattern 3: Programmatic Control

Use the watcher in your own Python scripts:

```python
from src.ingestion.file_watcher import SQLFileWatcher

# Create watcher
watcher = SQLFileWatcher(
    watch_dir="./data/raw",
    output_dir="./data/separated_sql",
    add_metadata=True,
    overwrite_existing=True,
    debounce_seconds=2.0
)

# Start watching
watcher.start(process_existing=True)

# Or start in background thread for integration
import threading
thread = threading.Thread(target=watcher.start, daemon=True)
thread.start()
```

**Best for**:
- Integration with existing applications
- Custom processing pipelines
- Automated workflows

## Configuration Options

### SQLFileWatcher Parameters

```python
SQLFileWatcher(
    watch_dir="./data/raw",           # Directory to watch
    output_dir="./data/separated_sql", # Output directory
    add_metadata=True,                 # Add metadata headers
    overwrite_existing=True,           # Overwrite existing files
    debounce_seconds=2.0              # Delay before processing
)
```

#### `watch_dir`
- **Type**: `str`
- **Default**: `"./data/raw"`
- **Description**: Directory to monitor for SQL files
- **Example**: `"/var/data/sql_imports"`

#### `output_dir`
- **Type**: `str`
- **Default**: `"./data/separated_sql"`
- **Description**: Base directory for organized output
- **Example**: `"/var/data/processed_sql"`

#### `add_metadata`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Whether to add metadata headers to separated files
- **Example**: `False` (for cleaner output)

#### `overwrite_existing`
- **Type**: `bool`
- **Default**: `True`
- **Description**: Whether to overwrite existing organized files
- **Example**: `False` (to preserve existing files)

#### `debounce_seconds`
- **Type**: `float`
- **Default**: `2.0`
- **Description**: Seconds to wait before processing after file change detected
- **Purpose**: Prevents duplicate processing when files are modified multiple times rapidly
- **Example**: `5.0` (for slower file systems or network drives)

## How It Works

### Architecture

```
┌─────────────────┐
│   data/raw/     │  <-- You add SQL files here
│  *.sql files    │
└────────┬────────┘
         │
         │ (File System Events)
         ▼
┌─────────────────────────┐
│   Watchdog Observer     │  <-- Monitors directory
│  (file_watcher.py)      │
└────────┬────────────────┘
         │
         │ (New/Modified .sql file)
         ▼
┌─────────────────────────┐
│   SQLFileHandler        │  <-- Filters events
│  - Debouncing           │
│  - .sql files only      │
└────────┬────────────────┘
         │
         │ (Process file)
         ▼
┌─────────────────────────┐
│ HierarchicalOrganizer   │  <-- Organizes file
│  - Parse SQL            │
│  - Detect objects       │
│  - Create folders       │
└────────┬────────────────┘
         │
         │ (Write files)
         ▼
┌─────────────────────────┐
│ data/separated_sql/     │  <-- Organized output
│  DatabaseName/          │
│    tables/              │
│    views/               │
│    functions/           │
│    stored_procedures/   │
└─────────────────────────┘
```

### Event Flow

1. **File Added/Modified**
   - User adds `database.sql` to `data/raw/`
   - File system triggers event

2. **Event Detection**
   - Watchdog observer detects event
   - Passes to `SQLFileHandler`

3. **Event Filtering**
   - Checks if file is `.sql`
   - Checks if not recently processed (debouncing)
   - Checks if not already being processed

4. **File Processing**
   - Calls `HierarchicalOrganizer.organize_file()`
   - Parses SQL using SQL Server comment patterns
   - Detects all objects (tables, views, functions, etc.)
   - Identifies parent-child relationships

5. **Folder Creation**
   - Creates folder: `data/separated_sql/database/`
   - Creates type folders: `tables/`, `views/`, etc.
   - Creates object folders: `Product/`, `Customer/`, etc.
   - Creates subfolders: `indexes/`, `foreign_keys/`, etc.

6. **File Writing**
   - Writes main object files
   - Writes related object files
   - Adds metadata headers
   - Generates manifest

7. **Logging**
   - Logs all activities
   - Reports errors
   - Shows statistics

### Debouncing Explained

File systems can trigger multiple events for a single file change. Debouncing prevents duplicate processing:

```
Without Debouncing:
File modified at 10:00:00.000
├─ Event 1: 10:00:00.001  -> Process file
├─ Event 2: 10:00:00.015  -> Process file (duplicate!)
└─ Event 3: 10:00:00.023  -> Process file (duplicate!)

With Debouncing (2 seconds):
File modified at 10:00:00.000
├─ Event 1: 10:00:00.001  -> Process file
├─ Event 2: 10:00:00.015  -> Skip (within 2 seconds)
└─ Event 3: 10:00:00.023  -> Skip (within 2 seconds)

File modified again at 10:00:03.000
└─ Event 4: 10:00:03.001  -> Process file (>2 seconds elapsed)
```

## Logging

The file watcher uses Python's standard logging module with comprehensive logging:

### Log Levels

- **INFO**: Normal operations (file detected, processing started, etc.)
- **WARNING**: Non-critical issues (no objects found, etc.)
- **ERROR**: Critical errors (parse failures, write errors, etc.)
- **DEBUG**: Detailed debugging information

### Example Log Output

```
2025-12-08 20:15:30 - __main__ - INFO - [INIT] File watcher initialized
2025-12-08 20:15:30 - __main__ - INFO - [INIT] Watching: C:\data\raw
2025-12-08 20:15:30 - __main__ - INFO - [INIT] Output: C:\data\separated_sql
2025-12-08 20:15:45 - __main__ - INFO - [NEW FILE] Detected: data\raw\MyDatabase.sql
2025-12-08 20:15:45 - __main__ - INFO - [PROCESSING] MyDatabase.sql
2025-12-08 20:15:48 - __main__ - INFO - [OK] Successfully processed: MyDatabase.sql
2025-12-08 20:15:48 - __main__ - INFO - [OK] Created 42 files
```

### Custom Logging Configuration

You can customize logging in your own scripts:

```python
import logging

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sql_watcher.log'),
        logging.StreamHandler()
    ]
)

from src.ingestion.file_watcher import SQLFileWatcher

watcher = SQLFileWatcher()
watcher.start()
```

## Integration with Pipeline

The file watcher is the first step in the data lineage pipeline:

```
┌──────────────┐
│  SQL Files   │
│  (data/raw/) │
└──────┬───────┘
       │
       │ (File Watcher)
       ▼
┌─────────────────────────┐
│  Organized Files        │
│  (data/separated_sql/)  │
└──────┬──────────────────┘
       │
       │ (Next Step: Entity Extraction)
       ▼
┌─────────────────────────┐
│  Entity Extractor       │
│  - Parse SQL            │
│  - Extract entities     │
│  - Extract relationships│
└──────┬──────────────────┘
       │
       │ (Next Step: Knowledge Graph)
       ▼
┌─────────────────────────┐
│  Graph Populator        │
│  - Create vertices      │
│  - Create edges         │
│  - Store in Cosmos DB   │
└──────┬──────────────────┘
       │
       │ (Next Step: Embeddings)
       ▼
┌─────────────────────────┐
│  Embedding Generator    │
│  - Semantic chunking    │
│  - Generate embeddings  │
│  - Store in AI Search   │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Query Interface        │
│  - Natural language     │
│  - Lineage queries      │
│  - Visualization        │
└─────────────────────────┘
```

## Error Handling

### Common Errors and Solutions

#### Error: `watchdog library not installed`

**Solution**:
```bash
pip install watchdog
```

#### Error: `Permission denied` when accessing watch directory

**Solution**:
- Check directory permissions
- Run with appropriate user permissions
- On Windows, check if directory is locked by another process

#### Error: `No objects found in file`

**Cause**: SQL file doesn't have SQL Server comment patterns

**Solution**:
- Ensure SQL file has `/****** Object: ... ******/` comments
- Use SQL Server Management Studio to generate scripts with headers
- Or use the basic organizer instead of hierarchical organizer

#### Error: `UnicodeDecodeError` when reading file

**Cause**: File encoding is not UTF-8

**Solution**:
- Convert file to UTF-8 encoding
- Or modify organizer to handle different encodings

## Performance Considerations

### Processing Time

Typical processing times:
- **Small file** (10-20 objects): 1-2 seconds
- **Medium file** (50-100 objects): 3-5 seconds
- **Large file** (200+ objects): 10-15 seconds

### Concurrent Processing

The watcher processes files sequentially to avoid conflicts. If multiple files are added simultaneously:

1. First file is processed immediately
2. Subsequent files are queued
3. Each file is processed after the previous completes

### Resource Usage

- **CPU**: Minimal when idle, moderate during processing
- **Memory**: Scales with file size (typically <100MB)
- **Disk I/O**: Moderate during processing
- **Network**: None (unless watch/output directories are network drives)

## Best Practices

### 1. Use Dedicated Directories

```
data/
  raw/              <-- Only .sql files here
  separated_sql/    <-- Output only
  archive/          <-- Move processed files here if needed
```

### 2. Clean Up Raw Directory Periodically

After processing, optionally move files to archive:

```bash
# After processing completes
mv data/raw/*.sql data/archive/
```

Or programmatically:

```python
import shutil
from pathlib import Path

for sql_file in Path("data/raw").glob("*.sql"):
    shutil.move(sql_file, f"data/archive/{sql_file.name}")
```

### 3. Monitor Logs

Always monitor logs for errors:

```bash
python examples/start_file_watcher.py 2>&1 | tee watcher.log
```

### 4. Test with Small Files First

Before processing large production files:
1. Test with small sample files
2. Verify output structure
3. Check for errors
4. Then process larger files

### 5. Use Version Control for Output

Consider version controlling the organized output:

```bash
cd data/separated_sql
git init
git add .
git commit -m "Initial SQL organization"
```

## Troubleshooting

### Issue: Watcher doesn't detect files

**Possible causes**:
- Wrong watch directory
- File extension is not `.sql`
- Permissions issue

**Debug**:
```python
from pathlib import Path
print(list(Path("./data/raw").glob("*.sql")))  # Check if files visible
```

### Issue: Processing very slow

**Possible causes**:
- Very large SQL files
- Network drive (slow I/O)
- Antivirus scanning files

**Solutions**:
- Process files locally
- Increase debounce time
- Exclude directories from antivirus

### Issue: Duplicate processing

**Cause**: Debounce time too short

**Solution**: Increase debounce time:
```python
watcher = SQLFileWatcher(debounce_seconds=5.0)
```

## Advanced Usage

### Running as Background Service

#### Linux/macOS (systemd)

Create `/etc/systemd/system/sql-watcher.service`:

```ini
[Unit]
Description=SQL File Watcher
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/financial-lineage-tool
ExecStart=/usr/bin/python3 examples/start_file_watcher.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable sql-watcher
sudo systemctl start sql-watcher
sudo systemctl status sql-watcher
```

#### Windows (Windows Service)

Use NSSM (Non-Sucking Service Manager):

```cmd
nssm install SQLWatcher "C:\Python\python.exe" "C:\path\to\examples\start_file_watcher.py"
nssm start SQLWatcher
```

### Integration with Docker

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  sql-watcher:
    build: .
    volumes:
      - ./data/raw:/app/data/raw
      - ./data/separated_sql:/app/data/separated_sql
    command: python examples/start_file_watcher.py
    restart: always
```

## Summary

The SQL File Watcher provides:

- ✅ **Automatic processing** - No manual intervention
- ✅ **Real-time monitoring** - Immediate detection of changes
- ✅ **Intelligent debouncing** - Avoids duplicate processing
- ✅ **Error resilience** - Continues monitoring after errors
- ✅ **Comprehensive logging** - Full visibility into operations
- ✅ **Easy integration** - Works with existing pipeline

## Next Steps

1. **Start the watcher**: `python examples/start_file_watcher.py`
2. **Test with sample files**: Copy SQL files to `data/raw/`
3. **Verify output**: Check `data/separated_sql/`
4. **Integrate with pipeline**: Connect to entity extraction → knowledge graph
5. **Deploy**: Run as background service in production

---

**Ready for automatic SQL file processing!**

