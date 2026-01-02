@echo off
REM ========================================================================
REM  Docker Installation Validation Script
REM ========================================================================

echo.
echo ================================================================
echo  Docker Installation Validation
echo ================================================================
echo.

REM Check Docker installation
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [X] Docker is NOT installed
    echo.
    echo Please install Docker Desktop from:
    echo https://www.docker.com/products/docker-desktop
    echo.
    goto :ollama_check
) else (
    echo [+] Docker is installed
)

REM Check Docker version
echo.
echo Docker version:
docker --version
echo.

REM Check if Docker daemon is running
docker info >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [X] Docker daemon is NOT running
    echo.
    echo Please start Docker Desktop
    echo.
    goto :ollama_check
) else (
    echo [+] Docker daemon is running
)

REM Check Docker Compose
echo.
docker compose version
if %ERRORLEVEL% NEQ 0 (
    echo [X] Docker Compose is NOT available
    goto :ollama_check
) else (
    echo [+] Docker Compose is available
)

REM Check available resources
echo.
echo [*] Checking system resources...
docker info | findstr "CPUs Memory"

REM Check disk space
echo.
echo [*] Disk space:
for /f "tokens=3" %%a in ('dir /-c ^| find "bytes free"') do set FREE_SPACE=%%a
echo   Free space: %FREE_SPACE% bytes

:ollama_check
REM Check Ollama
echo.
echo ================================================================
echo  Ollama Installation Check
echo ================================================================
echo.

where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [X] Ollama is NOT installed
    echo.
    echo Install Ollama from: https://ollama.ai
    echo.
    goto :summary
) else (
    echo [+] Ollama is installed
)

REM Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Ollama is installed but NOT running
    echo.
    echo Start Ollama with: ollama serve
    echo.
    goto :summary
) else (
    echo [+] Ollama is running
)

REM Check required models
echo.
echo [*] Checking required models...

curl -s http://localhost:11434/api/tags > %TEMP%\ollama_models.txt 2>nul
findstr "llama3.1:8b" %TEMP%\ollama_models.txt >nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Model llama3.1:8b is NOT available
    echo     Pull with: ollama pull llama3.1:8b
) else (
    echo [+] Model llama3.1:8b is available
)

findstr "nomic-embed-text" %TEMP%\ollama_models.txt >nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Model nomic-embed-text is NOT available
    echo     Pull with: ollama pull nomic-embed-text
) else (
    echo [+] Model nomic-embed-text is available
)

del %TEMP%\ollama_models.txt >nul 2>nul

:summary
echo.
echo ================================================================
echo  Summary
echo ================================================================
echo.
echo If all checks passed, you're ready to run:
echo   start-docker.bat
echo.
echo If any checks failed, address them before starting.
echo.
pause
