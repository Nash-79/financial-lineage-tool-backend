@echo off
REM ========================================================================
REM  View Docker Compose Logs
REM ========================================================================

echo.
echo [*] Viewing logs for all services...
echo     Press Ctrl+C to exit
echo.

docker compose -f docker-compose.yml logs -f --tail=100
