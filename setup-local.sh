#!/bin/bash

# ============================================================
# Financial Lineage Tool - Local Setup Script (FREE)
# ============================================================

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Financial Lineage Tool - FREE Local Setup                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "${RED}✗${NC} $1 not found"
        return 1
    fi
}

echo "Checking prerequisites..."
echo ""

check_command docker
check_command python3
OLLAMA_INSTALLED=$(check_command ollama && echo "yes" || echo "no")

echo ""

# Install Ollama if not present
if [ "$OLLAMA_INSTALLED" = "no" ]; then
    echo -e "${YELLOW}Installing Ollama...${NC}"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install ollama
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "Please install Ollama manually from https://ollama.com/download"
        exit 1
    fi
fi

# Start Ollama service
echo ""
echo -e "${YELLOW}Starting Ollama service...${NC}"
ollama serve &> /dev/null &
sleep 2

# Pull required models
echo ""
echo -e "${YELLOW}Pulling Ollama models (this may take a few minutes)...${NC}"
echo ""
echo "Pulling llama3.1:8b (4.7GB)..."
ollama pull llama3.1:8b

echo ""
echo "Pulling nomic-embed-text (274MB)..."
ollama pull nomic-embed-text

# Create Python virtual environment
echo ""
echo -e "${YELLOW}Setting up Python environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements-local.txt

# Create data directories
echo ""
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p data/repos
mkdir -p data/chunks
mkdir -p notebooks

# Start Docker services
echo ""
echo -e "${YELLOW}Starting Docker services (Qdrant, Gremlin)...${NC}"
docker-compose -f docker-compose.local.yml up -d gremlin-server qdrant

# Wait for services
echo ""
echo "Waiting for services to start..."
sleep 10

# Check services
echo ""
echo "Checking services..."
echo ""

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${GREEN}✓${NC} Ollama is running"
else
    echo -e "${RED}✗${NC} Ollama is not responding"
fi

# Check Qdrant
if curl -s http://localhost:6333/health > /dev/null; then
    echo -e "${GREEN}✓${NC} Qdrant is running"
else
    echo -e "${RED}✗${NC} Qdrant is not responding"
fi

# Check Gremlin
if curl -s http://localhost:8182 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Gremlin Server is running"
else
    echo -e "${YELLOW}!${NC} Gremlin Server may still be starting..."
fi

# Done!
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ${GREEN}Setup Complete!${NC}                                           ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║   To start the API:                                         ║"
echo "║   ${YELLOW}source venv/bin/activate${NC}                                  ║"
echo "║   ${YELLOW}python -m uvicorn src.api.main_local:app --reload${NC}         ║"
echo "║                                                              ║"
echo "║   Then visit: http://localhost:8000/docs                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Services:"
echo "  • API:      http://localhost:8000"
echo "  • Qdrant:   http://localhost:6333"
echo "  • Gremlin:  ws://localhost:8182"
echo "  • Ollama:   http://localhost:11434"
echo ""
