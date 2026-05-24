#!/bin/bash
cd "$(dirname "$0")"

TOKEN=$(grep '^META_ACCESS_TOKEN=' .env | cut -d= -f2-)

echo "══════════════════════════════════════════"
echo "   Meta API diagnostics"
echo "══════════════════════════════════════════"
echo ""

echo "1) Checking token validity..."
echo "   Testing against graph.instagram.com (Instagram Login tokens)..."
ME=$(curl -s "https://graph.instagram.com/v25.0/me?fields=id,username&access_token=$TOKEN")
echo "   $ME"
echo ""

echo "2) Also testing against graph.facebook.com..."
ME2=$(curl -s "https://graph.facebook.com/v25.0/me?fields=id,name&access_token=$TOKEN")
echo "   $ME2"
echo ""

echo "3) Subscribing 'messages' field on graph.instagram.com..."
SUB_RESULT=$(curl -s -X POST \
  "https://graph.instagram.com/v25.0/me/subscribed_apps" \
  -d "subscribed_fields=messages&access_token=$TOKEN")
echo "   $SUB_RESULT"
echo ""

echo "4) Subscribing 'messages' field on graph.facebook.com..."
SUB_RESULT2=$(curl -s -X POST \
  "https://graph.facebook.com/v25.0/me/subscribed_apps" \
  -d "subscribed_fields=messages&access_token=$TOKEN")
echo "   $SUB_RESULT2"
echo ""

echo "Done. Press Enter to exit."
read
