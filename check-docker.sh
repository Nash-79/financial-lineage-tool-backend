#!/bin/bash
# ========================================================================
#  Docker Installation Validation Script
# ========================================================================

echo ""
echo "================================================================"
echo " Docker Installation Validation"
echo "================================================================"
echo ""

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "[X] Docker is NOT installed"
    echo ""
    echo "Please install Docker from:"
    echo "https://docs.docker.com/get-docker/"
    echo ""
else
    echo "[+] Docker is installed"

    # Check Docker version
    echo ""
    echo "Docker version:"
    docker --version
    echo ""

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        echo "[X] Docker daemon is NOT running"
        echo ""
        echo "Please start Docker"
        echo ""
    else
        echo "[+] Docker daemon is running"

        # Check Docker Compose
        echo ""
        if docker compose version &> /dev/null; then
            echo "[+] Docker Compose is available"
            docker compose version
        else
            echo "[X] Docker Compose is NOT available"
        fi

        # Check available resources
        echo ""
        echo "[*] Checking system resources..."
        docker info | grep -E "CPUs|Total Memory"

        # Check disk space
        echo ""
        echo "[*] Disk space:"
        df -h . | tail -1
    fi
fi

# Check Ollama
echo ""
echo "================================================================"
echo " Ollama Installation Check"
echo "================================================================"
echo ""

if ! command -v ollama &> /dev/null; then
    echo "[X] Ollama is NOT installed"
    echo ""
    echo "Install Ollama from: https://ollama.ai"
    echo ""
else
    echo "[+] Ollama is installed"

    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo "[+] Ollama is running"

        # Check required models
        echo ""
        echo "[*] Checking required models..."

        models=$(curl -s http://localhost:11434/api/tags)

        if echo "$models" | grep -q "llama3.1:8b"; then
            echo "[+] Model llama3.1:8b is available"
        else
            echo "[!] Model llama3.1:8b is NOT available"
            echo "    Pull with: ollama pull llama3.1:8b"
        fi

        if echo "$models" | grep -q "nomic-embed-text"; then
            echo "[+] Model nomic-embed-text is available"
        else
            echo "[!] Model nomic-embed-text is NOT available"
            echo "    Pull with: ollama pull nomic-embed-text"
        fi
    else
        echo "[!] Ollama is installed but NOT running"
        echo ""
        echo "Start Ollama with: ollama serve"
        echo ""
    fi
fi

echo ""
echo "================================================================"
echo " Summary"
echo "================================================================"
echo ""
echo "If all checks passed, you're ready to run:"
echo "  ./start-docker.sh"
echo ""
echo "If any checks failed, address them before starting."
echo ""
