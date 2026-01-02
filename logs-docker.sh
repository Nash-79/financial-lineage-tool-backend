#!/bin/bash
# ========================================================================
#  View Docker Compose Logs
# ========================================================================

echo ""
echo "[*] Viewing logs for all services..."
echo "    Press Ctrl+C to exit"
echo ""

docker compose -f docker-compose.yml logs -f --tail=100
