@echo off
REM ================================================================
REM   Simple Startup Script - Minimal checks, direct execution
REM ================================================================

title Financial Lineage Tool

echo ================================================================
echo   Financial Lineage Tool - Starting API
echo ================================================================
echo.

REM Check if we're in the right directory
if not exist "src\api\main_local.py" (
    echo ERROR: Cannot find src\api\main_local.py
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Check virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Creating...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        echo Make sure Python is installed and in PATH
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
    echo.
)

echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

echo [*] Checking/Installing dependencies...
echo.

REM Install core dependencies individually with better error handling
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing FastAPI...
    pip install fastapi
)

pip show uvicorn >nul 2>&1
if errorlevel 1 (
    echo Installing Uvicorn...
    pip install "uvicorn[standard]"
)

pip show httpx >nul 2>&1
if errorlevel 1 (
    echo Installing httpx...
    pip install httpx
)

pip show python-dotenv >nul 2>&1
if errorlevel 1 (
    echo Installing python-dotenv...
    pip install python-dotenv
)

pip show neo4j >nul 2>&1
if errorlevel 1 (
    echo Installing neo4j driver...
    pip install neo4j
)

pip show sqlglot >nul 2>&1
if errorlevel 1 (
    echo Installing sqlglot...
    pip install sqlglot
)

pip show networkx >nul 2>&1
if errorlevel 1 (
    echo Installing networkx...
    pip install networkx
)

echo.
echo [OK] Core dependencies ready
echo.

REM Check services
echo ================================================================
echo   Checking Services
echo ================================================================
echo.

REM Check Ollama
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [!] WARNING: Ollama not responding at http://localhost:11434
    echo     Please start Ollama manually: ollama serve
    echo.
) else (
    echo [OK] Ollama is running
)

REM Check Qdrant
curl -s http://localhost:6333/health >nul 2>&1
if errorlevel 1 (
    echo [!] WARNING: Qdrant not responding at http://localhost:6333
    echo     Please start Qdrant manually
    echo.
) else (
    echo [OK] Qdrant is running
)

REM Check .env
if not exist ".env" (
    echo [!] WARNING: .env file not found
    echo     Neo4j credentials will need to be configured
    echo.
)

echo.
echo ================================================================
echo   Starting FastAPI Server
echo ================================================================
echo.
echo Server will be available at:
echo   - http://localhost:8000/docs  (Swagger UI)
echo   - http://localhost:8000/health (Health check)
echo.
echo Press Ctrl+C to stop
echo.
echo ================================================================
echo.

REM Start the server
python -m uvicorn src.api.main_local:app --host 0.0.0.0 --port 8000 --reload

pause
