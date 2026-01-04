@echo off
REM ========================================================================
REM  Financial Lineage Tool - Docker Compose Startup (Windows)
REM ========================================================================
REM  This is the PRIMARY and RECOMMENDED way to start the backend.
REM  Uses Docker Compose to orchestrate all services.
REM ========================================================================

echo.
echo ================================================================
echo  Financial Lineage Tool - Docker Compose Startup
echo ================================================================
echo.

REM Check if Docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not in PATH
    echo.
    echo Please install Docker Desktop from:
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

REM Check if Docker daemon is running
docker info >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker daemon is not running
    echo.
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

echo [*] Docker is installed and running
echo.

REM Check if Ollama is running (optional but recommended)
echo [*] Checking Ollama availability...
curl -s http://localhost:11434/api/tags >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] WARNING: Ollama is not running on localhost:11434
    echo [!] LLM features will not work until Ollama is started
    echo.
    echo To start Ollama:
    echo   1. Install from: https://ollama.ai
    echo   2. Run: ollama serve
    echo   3. Pull required models:
    echo      ollama pull llama3.1:8b
    echo      ollama pull nomic-embed-text
    echo.
) else (
    echo [+] Ollama is running
)

echo.
echo [*] Starting services with Docker Compose...
echo.

REM Start Docker Compose
docker compose up -d

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start Docker Compose
    echo.
    echo Check the error messages above for details.
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  Services Started Successfully!
echo ================================================================
echo.
echo  API:      http://localhost:8000
echo  Docs:     http://localhost:8000/docs
echo  Health:   http://localhost:8000/health
echo  Qdrant:   http://localhost:6333
echo  Redis:    localhost:6379
echo  Jupyter:  http://localhost:8888
echo.
echo  To view logs:    logs-docker.bat
echo  To stop:         stop-docker.bat
echo  To restart API:  docker compose restart api
echo.
echo ================================================================
echo.

REM Wait for health check
echo [*] Waiting for API to be healthy (max 60 seconds)...
set /a timeout=60
set /a count=0

:healthcheck
timeout /t 2 /nobreak >nul
curl -s -f http://localhost:8000/health >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [+] API is healthy!
    goto :healthy
)
set /a count+=2
if %count% LSS %timeout% goto :healthcheck

echo [!] WARNING: API health check timed out
echo [!] Check logs with: logs-docker.bat

:healthy
echo.
echo Press any key to view logs, or Ctrl+C to exit...
pause >nul
call logs-docker.bat
