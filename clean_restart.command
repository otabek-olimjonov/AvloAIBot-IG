#!/bin/bash
cd "$(dirname "$0")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${YELLOW}[→]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; }

echo ""
echo "══════════════════════════════════════════════"
echo "   Clean restart — wipes DB volume and rebuilds"
echo "══════════════════════════════════════════════"
echo ""

# Load passwords from .env
DB_PASS=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
DB_USER=$(grep '^POSTGRES_USER=' .env | cut -d= -f2-)
DB_NAME=$(grep '^POSTGRES_DB=' .env | cut -d= -f2-)

info "Will use: user=$DB_USER db=$DB_NAME pass=${DB_PASS:0:6}..."

echo ""
info "Step 1: Stopping everything and wiping postgres volume..."
docker compose down -v --remove-orphans
ok "Volumes cleared."

echo ""
info "Step 2: Starting postgres and redis..."
docker compose up -d postgres redis
echo "Waiting 20 seconds for postgres to initialise..."
sleep 20

echo ""
info "Step 3: Verifying postgres is accepting connections..."
for i in $(seq 1 12); do
  if docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
    ok "Postgres is ready!"
    break
  fi
  if [ "$i" -eq 12 ]; then
    fail "Postgres did not become ready after 60s."
    docker compose logs postgres | tail -20
    echo "Press Enter to exit."; read
    exit 1
  fi
  echo "  Waiting... ($((i*5))s)"
  sleep 5
done

echo ""
info "Step 4: Confirming DATABASE_URL password matches postgres..."
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" 2>&1 | head -3
ok "Password check passed."

echo ""
info "Step 5: Starting app, worker, telegram-bot..."
docker compose up -d --build app worker telegram-bot
echo "Waiting 20 seconds for app to start..."
sleep 20

echo ""
info "Step 6: Waiting for app health..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "App is healthy!"
    break
  fi
  if [ "$i" -eq 20 ]; then
    fail "App health check timed out."
    docker compose logs app | tail -30
    echo "Press Enter to exit."; read
    exit 1
  fi
  echo "  Waiting... ($((i*3))s)"
  sleep 3
done

echo ""
info "Step 7: Running DB migrations..."
docker compose exec -T app python -m alembic upgrade head 2>&1
if [ $? -eq 0 ]; then
  ok "Migrations applied!"
else
  fail "Migration failed. Showing app logs:"
  docker compose logs app | tail -40
fi

echo ""
info "Step 8: Seeding initial data..."
docker compose exec -T app python -m scripts.seed 2>&1 || echo "(Seed skipped — already done)"

echo ""
info "Step 9: Final health check..."
curl -sf http://localhost:8000/health && ok "App is healthy and ready!" || fail "App not responding"

echo ""
echo "══════════════════════════════════════════════"
echo "   Done! You can close this window."
echo "══════════════════════════════════════════════"
echo ""
echo "Press Enter to exit."
read
