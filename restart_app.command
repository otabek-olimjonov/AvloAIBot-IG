#!/bin/bash
cd "$(dirname "$0")"
echo "Rebuilding and restarting app container..."
docker compose up -d --build app worker telegram-bot
echo ""
echo "Done! Checking app health..."
sleep 5
curl -sf http://localhost:8000/health && echo "App is healthy!" || echo "App still starting, check: docker compose logs app"
