# Troubleshooting Guide

## Issue: http://localhost:8000/docs is not working

### Quick Diagnostics

Run these commands to check what's wrong:

```bash
# 1. Check if API is running
curl http://localhost:8000/health

# 2. Check if port 8000 is in use
netstat -ano | findstr ":8000"

# 3. Check Python processes
tasklist | findstr "python"
```

### Common Issues

#### 1. Dependencies Not Installed

**Symptoms:** ModuleNotFoundError when starting the API

**Solution:**
```bash
# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install minimal dependencies for local dev
pip install fastapi uvicorn pydantic httpx python-dotenv neo4j sqlglot networkx
```

#### 2. Ollama Not Running

**Symptoms:** "Ollama not available" errors

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve

# Pull required models
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

#### 3. Qdrant Not Running

**Symptoms:** Qdrant connection errors

**Solution:**
```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# If not, start it (from qdrant directory)
cd qdrant
qdrant.exe
```

#### 4. Neo4j Connection Issues

**Symptoms:** "Failed to connect to Neo4j" errors

**Solution:**
- Check `.env` file exists and has correct credentials
- Verify Neo4j credentials:
  - NEO4J_URI
  - NEO4J_USERNAME
  - NEO4J_PASSWORD
  - NEO4J_DATABASE

#### 5. Port 8000 Already in Use

**Symptoms:** "Address already in use" error

**Solution:**
```bash
# Find process using port 8000
netstat -ano | findstr ":8000"

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use a different port
python -m uvicorn src.api.main_local:app --host 0.0.0.0 --port 8001
```

#### 6. Idempotency Not Clearing Old Chunks

**Symptoms:** Re-ingesting a file shows duplicate or stale results.

**Solution:**
```bash
# Verify the file_path matches exactly (case-sensitive)
# Check Qdrant payloads for the stored file_path
curl http://localhost:6333/collections/code_chunks/points/scroll -H "Content-Type: application/json" -d "{\"limit\": 1, \"with_payload\": true}"
```
- Ensure the ingestion request uses the same `file_path` value each time.
- Confirm Neo4j nodes include `source_file` matching the ingested path.

#### 7. Plugin Not Loaded

**Symptoms:** Logs show "No lineage plugin registered for extension" or parsing is skipped.

**Solution:**
```bash
# Confirm plugin list
echo %LINEAGE_PLUGINS%

# Check plugin config JSON
echo %LINEAGE_PLUGIN_CONFIG_JSON%
```
- Make sure the class paths are correct.
- Remove trailing commas from `LINEAGE_PLUGINS`.
- Validate JSON in `LINEAGE_PLUGIN_CONFIG_JSON`.

#### 8. Tree-sitter Import Errors

**Symptoms:** `ModuleNotFoundError: tree_sitter` or `tree_sitter_python`.

**Solution:**
```bash
pip install tree-sitter tree-sitter-python
```

### Manual Start (Bypassing Batch Script)

If `start-local.bat` isn't working, try manual startup:

```bash
# 1. Activate virtual environment
venv\Scripts\activate

# 2. Set environment variables (optional)
set OLLAMA_HOST=http://localhost:11434
set QDRANT_HOST=localhost
set QDRANT_PORT=6333

# 3. Start the API
python -m uvicorn src.api.main_local:app --host 0.0.0.0 --port 8000 --reload
```

### Check Service Status

```bash
# Ollama
curl http://localhost:11434/api/tags

# Qdrant
curl http://localhost:6333/health

# API (after starting)
curl http://localhost:8000/health
```

### View API Logs

If the API starts but crashes immediately, check the console output for error messages.

Common errors:
- **ModuleNotFoundError**: Missing dependencies - run `pip install -r requirements.txt`
- **Connection refused (Neo4j)**: Check .env credentials
- **Connection refused (Qdrant)**: Start Qdrant service
- **Connection refused (Ollama)**: Start Ollama service

### Fresh Start

If all else fails, try a complete reset:

```bash
# 1. Delete virtual environment
rmdir /s /q venv

# 2. Create new virtual environment
python -m venv venv

# 3. Activate it
venv\Scripts\activate

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt

# 6. Start services manually (see above)
```

### Alternative: Run Without Batch Script

Create a simple PowerShell script `start.ps1`:

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Start API
python -m uvicorn src.api.main_local:app --host 0.0.0.0 --port 8000 --reload
```

Then run:
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

### Getting Help

If you're still stuck, provide:
1. Output of `pip list`
2. Output of service status checks (Ollama, Qdrant, Neo4j)
3. Full error message from API startup
4. Contents of `.env` file (redacted passwords)
