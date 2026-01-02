#!/bin/bash
# ========================================================================
#  Financial Lineage Tool - Docker Compose Startup (Unix/Linux/macOS)
# ========================================================================
#  This is the PRIMARY and RECOMMENDED way to start the backend.
#  Uses Docker Compose to orchestrate all services.
# ========================================================================

set -e  # Exit on error

echo ""
echo "================================================================"
echo " Financial Lineage Tool - Docker Compose Startup"
echo "================================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed"
    echo ""
    echo "Please install Docker from:"
    echo "https://docs.docker.com/get-docker/"
    echo ""
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "[ERROR] Docker daemon is not running"
    echo ""
    echo "Please start Docker and try again."
    echo ""
    exit 1
fi

echo "[*] Docker is installed and running"
echo ""

# Check if Ollama is running (optional but recommended)
echo "[*] Checking Ollama availability..."
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "[+] Ollama is running"
else
    echo "[!] WARNING: Ollama is not running on localhost:11434"
    echo "[!] LLM features will not work until Ollama is started"
    echo ""
    echo "To start Ollama:"
    echo "  1. Install from: https://ollama.ai"
    echo "  2. Run: ollama serve"
    echo "  3. Pull required models:"
    echo "     ollama pull llama3.1:8b"
    echo "     ollama pull nomic-embed-text"
    echo ""
fi

echo ""
echo "[*] Starting services with Docker Compose..."
echo ""

# Start Docker Compose
docker compose -f docker-compose.yml up -d --build

echo ""
echo "================================================================"
echo " Services Started Successfully!"
echo "================================================================"
echo ""
echo "  API:      http://localhost:8000"
echo "  Docs:     http://localhost:8000/docs"
echo "  Health:   http://localhost:8000/health"
echo "  Qdrant:   http://localhost:6333"
echo "  Redis:    localhost:6379"
echo "  Jupyter:  http://localhost:8888"
echo ""
echo "  To view logs:    ./logs-docker.sh"
echo "  To stop:         ./stop-docker.sh"
echo "  To restart API:  docker compose -f docker-compose.yml restart api"
echo ""
echo "================================================================"
echo ""

# Wait for health check
echo "[*] Waiting for API to be healthy (max 60 seconds)..."
timeout=60
count=0

while [ $count -lt $timeout ]; do
    if curl -s -f http://localhost:8000/health &> /dev/null; then
        echo "[+] API is healthy!"
        break
    fi
    sleep 2
    count=$((count + 2))
done

if [ $count -ge $timeout ]; then
    echo "[!] WARNING: API health check timed out"
    echo "[!] Check logs with: ./logs-docker.sh"
fi

echo ""
echo "View logs? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    ./logs-docker.sh
fi
