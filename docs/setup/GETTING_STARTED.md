# Getting Started

Note: This guide uses the legacy organizer workflow (`data/raw` -> `data/separated_sql`).
For run-scoped ingestion (projects/runs and ingestion artifacts), see `../ingestion/INGESTION_OVERVIEW.md`.

## Quick Start

### 1. Installation

```bash
# Clone repository
cd financial-lineage-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Organize SQL Files

```bash
# Place SQL files in data/raw/
cp your_database.sql data/raw/

# Option A: One-time processing
python examples/test_hierarchical_organizer.py

# Option B: Start file watcher (automatic processing)
python examples/start_file_watcher.py
```

### Utility Scripts

```bash
# Ingest entire corpus (SQL, Python, JSON)
python scripts/ingest_corpus.py --dir data/raw
```

### 3. Check Output

```bash
# Organized files will be in:
data/separated_sql/your_database/
  tables/
  views/
  functions/
  stored_procedures/
```

## Next Steps

- **[Local Setup Guide](LOCAL_SETUP_GUIDE.md)**: Detailed environment setup.
- **[Docker Services](DOCKER_SERVICES.md)**: Understanding the container stack.
- **[Architecture](../architecture/ARCHITECTURE.md)**: System design and components.
