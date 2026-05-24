#!/bin/bash
cd "$(dirname "$0")"

echo "Testing DB connection..."

# Test with current password from .env
PASS=$(grep POSTGRES_PASSWORD .env | cut -d= -f2)
echo "Trying password from .env: $PASS"

docker compose exec -T postgres psql -U botuser -d instagram_bot -c "SELECT 1;" 2>/dev/null && {
  echo "✓ DB connection OK with current password"
} || {
  echo "✗ DB connection failed — recreating postgres volume with correct password"
  echo ""
  echo "Stopping containers and removing postgres volume..."
  docker compose down -v
  echo "Restarting with correct credentials..."
  docker compose up -d postgres redis
  echo "Waiting for postgres to be ready..."
  sleep 15
  docker compose up -d app worker telegram-bot
  echo "Waiting for app..."
  sleep 10
}

echo ""
echo "Running migrations..."
docker compose exec -T app python -m alembic upgrade head && echo "✓ Migrations done!" || echo "✗ Migration failed"

echo ""
echo "Seeding..."
docker compose exec -T app python -m scripts.seed && echo "✓ Seeded!" || echo "! Seed skipped (already done)"

echo ""
echo "Health check..."
curl -sf http://localhost:8000/health && echo " ← App is healthy!" || echo "App not responding on port 8000"

echo ""
echo "Done! You can close this window."
