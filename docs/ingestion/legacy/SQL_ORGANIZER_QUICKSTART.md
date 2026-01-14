# SQL File Organizer - Quick Start Guide

Note: This guide covers the legacy organizer workflow (`data/raw` -> `data/separated_sql`).
For the run-scoped ingestion pipeline, see `../INGESTION_OVERVIEW.md`.

## Overview

The SQL File Organizer automatically separates your SQL files into clean, organized folder structures. Each source SQL file gets its own folder with all objects categorized by type.

## Folder Structure

```
financial-lineage-tool/
  data/
    raw/                                      <-- Place your SQL files here
      AdventureWorksLT-All.sql
      sample_financial_schema.sql
      your_database_schema.sql

    separated_sql/                            <-- Organized output (auto-generated)
      AdventureWorksLT-All/                   <-- Folder per source file
        tables/
          Product.sql
          Customer.sql
          Address.sql
        views/
          vProductAndDescription.sql
        functions/
          ufnGetAllCategories.sql
        stored_procedures/
          Product_Insert.sql
          Product_Update.sql

      sample_financial_schema/                <-- Folder per source file
        tables/
          customers_clean.sql
          dim_customer.sql
          fact_transactions.sql
        views/
          customer_ltv_analysis.sql

      your_database_schema/                   <-- Your files here
        tables/
        views/
        ...

      separation_manifest.json                <-- Processing log
```

## Quick Start (3 Steps)

### Step 1: Add SQL Files to `data/raw/`

```bash
# Copy your SQL files to the raw folder
cp your_schema.sql financial-lineage-tool/data/raw/
cp stored_procedures.sql financial-lineage-tool/data/raw/
```

Or on Windows:
```cmd
copy your_schema.sql financial-lineage-tool\data\raw\
```

### Step 2: Run the Organizer

```bash
cd financial-lineage-tool
python examples/test_new_structure.py
```

Or use the organizer directly:

```python
from src.ingestion.sql_file_organizer import organize_sql_files

organize_sql_files(
    input_dir="./data/raw",
    output_dir="./data/separated_sql"
)
```

### Step 3: Check Results

```bash
# View the organized structure
ls data/separated_sql/

# Check a specific source file's objects
ls data/separated_sql/your_schema/tables/
ls data/separated_sql/your_schema/views/
ls data/separated_sql/your_schema/stored_procedures/
```

## What Gets Organized

The organizer extracts and separates:

- ✅ **Tables** → `tables/`
- ✅ **Views** → `views/`
- ✅ **Functions** → `functions/`
- ✅ **Stored Procedures** → `stored_procedures/`
- ✅ **Triggers** → `triggers/`
- ✅ **Indexes** → `indexes/`
- ✅ **Schemas** → `schemas/`

## Example

### Input File: `data/raw/my_database.sql`

```sql
-- Multiple objects in one file

CREATE TABLE dbo.customers (
    customer_id INT PRIMARY KEY,
    name VARCHAR(100)
);

CREATE VIEW dbo.vw_active_customers AS
SELECT * FROM dbo.customers WHERE active = 1;

CREATE FUNCTION dbo.get_customer_name(@id INT)
RETURNS VARCHAR(100)
AS BEGIN
    RETURN (SELECT name FROM dbo.customers WHERE customer_id = @id);
END;

CREATE PROCEDURE dbo.usp_update_customer
    @customer_id INT,
    @name VARCHAR(100)
AS BEGIN
    UPDATE dbo.customers SET name = @name WHERE customer_id = @customer_id;
END;
```

### Output: `data/separated_sql/my_database/`

After running the organizer:

```
data/separated_sql/
  my_database/
    tables/
      customers.sql                    <-- Just the table
    views/
      vw_active_customers.sql          <-- Just the view
    functions/
      get_customer_name.sql            <-- Just the function
    stored_procedures/
      usp_update_customer.sql          <-- Just the procedure
```

Each file contains only its object with metadata:

**`data/separated_sql/my_database/tables/customers.sql`**:
```sql
-- ============================================
-- Object Type: TABLE
-- Object Name: dbo.customers
-- Source File: my_database.sql
-- Separated On: 2025-12-08 18:54:04
-- Dialect: tsql
-- ============================================

CREATE TABLE dbo.customers (
    customer_id INT PRIMARY KEY,
    name VARCHAR(100)
);
```

## Real-World Example

We included sample SQL files. Test them:

```bash
cd financial-lineage-tool
python examples/test_new_structure.py
```

This processes:
1. **AdventureWorksLT-All.sql** (32 objects)
   - 10 tables
   - 3 views
   - 3 functions
   - 15 stored procedures
   - 1 schema

2. **sample_financial_schema.sql** (7 objects)
   - 6 tables
   - 1 view

Results in:
```
data/separated_sql/
  AdventureWorksLT-All/
    tables/ (10 files)
    views/ (3 files)
    functions/ (3 files)
    stored_procedures/ (15 files)
    schemas/ (1 file)

  sample_financial_schema/
    tables/ (6 files)
    views/ (1 file)
```

## Python API Usage

### Basic Usage

```python
from src.ingestion.sql_file_organizer import organize_sql_files

# Organize all SQL files in data/raw/
results = organize_sql_files(
    input_dir="./data/raw",
    output_dir="./data/separated_sql",
    dialect="tsql",
    pattern="*.sql",
    create_source_folders=True  # Creates folder per source file
)

# Check statistics
print(f"Files processed: {results['stats']['files_processed']}")
print(f"Objects separated: {results['stats']['objects_separated']}")
```

### Advanced: Single File

```python
from src.ingestion.sql_file_organizer import SQLFileOrganizer

organizer = SQLFileOrganizer(
    output_base_dir="./data/separated_sql",
    dialect="tsql",
    add_metadata_header=True,
    overwrite_existing=False,
    create_source_folders=True
)

# Organize one file
created = organizer.organize_file("./data/raw/my_schema.sql")

print(created)  # Shows created files by type
```

### Custom Configuration

```python
organizer = SQLFileOrganizer(
    output_base_dir="./custom_output",
    dialect="postgres",              # PostgreSQL
    add_metadata_header=False,       # No headers
    overwrite_existing=True,         # Overwrite
    create_source_folders=True       # Folder per source
)
```

## Supported SQL Dialects

- `tsql` - Microsoft SQL Server (T-SQL) ← Default
- `postgres` - PostgreSQL
- `mysql` - MySQL
- `oracle` - Oracle
- `bigquery` - Google BigQuery
- `snowflake` - Snowflake
- `sqlite` - SQLite

## Command-Line Usage

```bash
# Basic usage
python src/ingestion/sql_file_organizer.py ./data/raw ./data/separated_sql

# With custom pattern
python src/ingestion/sql_file_organizer.py ./data/raw ./output "*.ddl"
```

## Separation Manifest

Every run generates `separation_manifest.json`:

```json
{
  "generated_at": "2025-12-08T18:54:04.123456",
  "output_directory": "data/separated_sql",
  "dialect": "tsql",
  "statistics": {
    "files_processed": 2,
    "objects_separated": 39,
    "by_type": {
      "table": 16,
      "view": 4,
      "function": 3,
      "procedure": 15,
      "schema": 1
    },
    "errors": []
  },
  "files_by_type": {
    "table": [
      "AdventureWorksLT-All/tables/Product.sql",
      "AdventureWorksLT-All/tables/Customer.sql",
      ...
    ],
    ...
  }
}
```

## Features

### 1. Intelligent Parsing
- Uses `sqlglot` for AST-based parsing
- Falls back to regex for complex SQL
- Handles multiple dialects

### 2. Source File Organization
- Each source SQL file gets its own folder
- Easy to trace objects back to source
- No mixing of objects from different files

### 3. Metadata Tracking
- Each separated file includes source information
- Timestamps for traceability
- Dialect information preserved

### 4. Duplicate Handling
- Automatic versioning (file_v1.sql, file_v2.sql)
- Option to overwrite existing files
- No data loss

### 5. Error Recovery
- Continues processing even if one file fails
- Logs all errors in manifest
- Partial results still usable

## Troubleshooting

### "No SQL files found"
- Ensure files are in `data/raw/` folder
- Check file extension is `.sql`
- Verify file pattern matches

### "Sqlglot parsing failed"
- This is normal for complex SQL
- Organizer falls back to regex automatically
- Check manifest for details

### Empty object names (`.sql`)
- Some old SQL scripts don't name objects explicitly
- Files will be versioned (`.sql_v1`, `.sql_v2`)
- You may need to rename manually

### Unicode errors on Windows
- Tool uses ASCII-safe characters
- If issues persist, set: `PYTHONIOENCODING=utf-8`

## Next Steps

After organizing your SQL files:

1. **Set up File Watcher** (Auto-process new files)
   - See next component in roadmap

2. **Generate Embeddings** (For semantic search)
   - Feed separated files to chunker
   - Create vector embeddings

3. **Build Knowledge Graph** (Track lineage)
   - Extract entities from separated files
   - Create relationships in Cosmos DB

4. **Query with Natural Language**
   - Use multi-agent system
   - Get column-level lineage

## Summary

✅ **Place SQL files in**: `data/raw/`
✅ **Run**: `python examples/test_new_structure.py`
✅ **Check results in**: `data/separated_sql/`
✅ **Each source file gets its own folder**
✅ **Objects organized by type**
✅ **Ready for lineage analysis**

## Support

- Full documentation: `SQL_ORGANIZER_GUIDE.md`
- Architecture: `ARCHITECTURE.md`
- Examples: `examples/test_new_structure.py`

**Ready to organize? Add SQL files to `data/raw/` and run the script!**

