@echo off
REM ========================================================================
REM  Stop Docker Compose Services
REM ========================================================================

echo.
echo [*] Stopping Financial Lineage Tool services...
echo.

docker compose -f docker-compose.yml down

echo.
echo [+] Services stopped
echo.
echo To remove volumes (delete data), run:
echo   docker compose -f docker-compose.yml down -v
echo.
