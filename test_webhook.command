#!/bin/bash
cd "$(dirname "$0")"

APP_SECRET=$(grep '^META_APP_SECRET=' .env | cut -d= -f2-)

# Build a realistic DM payload
PAYLOAD='{"object":"instagram","entry":[{"id":"26894460353546735","time":1748123456,"messaging":[{"sender":{"id":"9999999999999"},"recipient":{"id":"26894460353546735"},"timestamp":1748123456789,"message":{"mid":"test_mid_001","text":"Hello! What products do you have?"}}]}]}'

# Calculate HMAC-SHA256 signature using Python (more reliable on macOS)
SIG=$(python3 -c "
import hmac, hashlib
secret = '$APP_SECRET'.encode()
payload = '$PAYLOAD'.encode()
sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
print(sig)
")

echo "════════════════════════════════════════"
echo "   Simulating Instagram DM webhook"
echo "════════════════════════════════════════"
echo ""
echo "Payload: $PAYLOAD"
echo "Signature: sha256=$SIG"
echo ""
echo "Sending POST to http://localhost:8000/api/v1/webhook/instagram ..."
echo ""

RESPONSE=$(curl -s -w "\n\nHTTP Status: %{http_code}" \
  -X POST http://localhost:8000/api/v1/webhook/instagram \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -d "$PAYLOAD")

echo "$RESPONSE"
echo ""
echo "════════════════════════════════════════"
echo "Check the check_logs.command window to"
echo "see if the app processed the message!"
echo "════════════════════════════════════════"
echo ""
echo "Press Enter to exit."
read
