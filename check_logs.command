#!/bin/bash
cd "$(dirname "$0")"
echo "═══════════════════════════════════════════"
echo "   App health + live logs (Ctrl+C to stop)"
echo "═══════════════════════════════════════════"
echo ""

# Health check
STATUS=$(curl -sf http://localhost:8000/health 2>/dev/null)
if [ "$STATUS" ]; then
  echo "✓ App healthy: $STATUS"
else
  echo "✗ App not responding on port 8000"
fi
echo ""

# Show recent app logs then follow
echo "--- Live app logs (waiting for webhook hits) ---"
docker compose logs --tail=20 -f app worker 2>&1
