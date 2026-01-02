@echo off
REM ================================================================
REM   Financial Lineage Tool - Local Startup Script (Windows)
REM   ** DEPRECATED - Use start-docker.bat instead **
REM ================================================================
REM
REM   This script starts services manually without Docker.
REM
REM   RECOMMENDED: Use start-docker.bat for a better experience with:
REM   - Automatic service orchestration
REM   - Health checks and dependency management
REM   - Easier debugging and monitoring
REM   - Production-ready configuration
REM
REM ================================================================

title Financial Lineage Tool - Startup (Legacy)

echo.
echo ================================================================
echo   Financial Lineage Tool - Local Development (LEGACY)
echo ================================================================
echo.
echo [!] DEPRECATION WARNING:
echo [!] This manual startup method is deprecated.
echo [!]
echo [!] RECOMMENDED: Use Docker Compose instead:
echo [!]   start-docker.bat
echo [!]
echo [!] Benefits of Docker Compose:
echo [!]   - Automatic service orchestration
echo [!]   - Health checks and dependencies
echo [!]   - Easier setup and debugging
echo [!]   - Production-ready configuration
echo.
echo Press Ctrl+C to exit, or any key to continue with manual startup...
pause >nul
echo.

REM Check if .env file exists
if not exist .env (
    echo [!] WARNING: .env file not found
    echo [!] Creating .env from .env.example...
    if exist .env.example (
        copy .env.example .env >nul
        echo [+] Created .env file. Please edit it with your credentials.
        echo.
        pause
    ) else (
        echo [!] ERROR: .env.example not found
        echo [!] Please create .env file with your Neo4j credentials
        pause
        exit /b 1
    )
)

REM ================================================================
REM Step 1: Check Ollama
REM ================================================================
echo [1/5] Checking Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo [!] ERROR: Ollama is not installed
    echo [!] Please install Ollama from: https://ollama.com/download
    echo [!] Then pull the required models:
    echo [!]   ollama pull llama3.1:8b
    echo [!]   ollama pull nomic-embed-text
    pause
    exit /b 1
)

REM Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [i] Starting Ollama service...
    start "Ollama Service" /MIN ollama serve
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Ollama is running
)

REM Check required models
echo [i] Checking Ollama models...
ollama list | findstr "llama3.1:8b" >nul 2>&1
if errorlevel 1 (
    echo [!] WARNING: llama3.1:8b model not found
    echo [!] Pulling llama3.1:8b model (this may take a few minutes)...
    ollama pull llama3.1:8b
)

ollama list | findstr "nomic-embed-text" >nul 2>&1
if errorlevel 1 (
    echo [!] WARNING: nomic-embed-text model not found
    echo [!] Pulling nomic-embed-text model...
    ollama pull nomic-embed-text
)

echo [OK] Ollama models ready
echo.

REM ================================================================
REM Step 2: Check Qdrant
REM ================================================================
echo [2/5] Checking Qdrant...
where qdrant >nul 2>&1
if errorlevel 1 (
    REM Check if Qdrant executable exists in qdrant folder
    if exist qdrant\qdrant.exe (
        echo [OK] Found Qdrant executable

        REM Check if Qdrant is running
        curl -s http://localhost:6333/health >nul 2>&1
        if errorlevel 1 (
            echo [i] Starting Qdrant...
            start "Qdrant Server" /MIN cmd /c "cd qdrant && qdrant.exe"
            timeout /t 5 /nobreak >nul
        ) else (
            echo [OK] Qdrant is already running
        )
    ) else (
        echo [!] ERROR: Qdrant not found
        echo [!] Please download Qdrant from: https://github.com/qdrant/qdrant/releases
        echo [!] Extract qdrant.exe to the 'qdrant' folder
        pause
        exit /b 1
    )
) else (
    REM Qdrant is in PATH, check if running
    curl -s http://localhost:6333/health >nul 2>&1
    if errorlevel 1 (
        echo [i] Starting Qdrant...
        start "Qdrant Server" /MIN qdrant
        timeout /t 5 /nobreak >nul
    ) else (
        echo [OK] Qdrant is already running
    )
)

REM Verify Qdrant is responding
curl -s http://localhost:6333/health >nul 2>&1
if errorlevel 1 (
    echo [!] WARNING: Qdrant may not have started successfully
    echo [!] Check that port 6333 is available
) else (
    echo [OK] Qdrant is responding
)
echo.

REM ================================================================
REM Step 3: Check Python Environment
REM ================================================================
echo [3/5] Checking Python environment...
if not exist venv (
    echo [!] Virtual environment not found. Creating...
    python -m venv venv
    if errorlevel 1 (
        echo [!] ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [!] ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM ================================================================
REM Step 4: Install Dependencies
REM ================================================================
echo [4/5] Checking Python dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [i] Installing dependencies from requirements.txt...
    pip install -q -r requirements.txt
    if errorlevel 1 (
        echo [!] ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)
echo [OK] Dependencies ready
echo.

REM ================================================================
REM Step 5: Create Data Directory
REM ================================================================
echo [5/5] Setting up data directories...
if not exist data (
    mkdir data
)
if not exist data\README.md (
    echo Creating data directory structure...
)
echo [OK] Data directories ready
echo.

REM ================================================================
REM Service Status Summary
REM ================================================================
echo ================================================================
echo   Service Status Check
echo ================================================================
echo.

REM Ollama
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [X] Ollama:  NOT RESPONDING
) else (
    echo [OK] Ollama:  http://localhost:11434
)

REM Qdrant
curl -s http://localhost:6333/health >nul 2>&1
if errorlevel 1 (
    echo [X] Qdrant:  NOT RESPONDING
) else (
    echo [OK] Qdrant:  http://localhost:6333
)

REM Neo4j (will be checked when API starts)
echo [i] Neo4j:   Cloud (will connect on API startup)

echo.

REM ================================================================
REM Start the API Server
REM ================================================================
echo ================================================================
echo   Starting FastAPI Server
echo ================================================================
echo.
echo API will be available at:
echo   - Swagger UI: http://localhost:8000/docs
echo   - API:        http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.
echo ================================================================
echo.

python -m uvicorn src.api.main_local:app --host 0.0.0.0 --port 8000 --reload

REM If we get here, the server was stopped
echo.
echo [i] Server stopped
pause
