#!/bin/bash
set -e

# ─── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║    AvloAI Instagram Bot - Launcher   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ─── Check Docker ─────────────────────────────────────────────────────────────
info "Checking Docker..."
if ! command -v docker &>/dev/null; then
  err "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
fi
if ! docker info &>/dev/null; then
  err "Docker is not running. Please start Docker Desktop and try again."
fi
log "Docker is running."

# ─── Install cloudflared ──────────────────────────────────────────────────────
info "Checking cloudflared (tunnel tool)..."
if ! command -v cloudflared &>/dev/null; then
  info "Installing cloudflared via Homebrew..."
  if ! command -v brew &>/dev/null; then
    err "Homebrew not found. Install it from https://brew.sh then re-run this script."
  fi
  brew install cloudflare/cloudflare/cloudflared
fi
log "cloudflared is ready."

# ─── Start Docker services ────────────────────────────────────────────────────
info "Starting all services (this may take a few minutes on first run)..."
cd "$(dirname "$0")"
docker compose up -d --build
log "All Docker services started."

# ─── Wait for app to be healthy ───────────────────────────────────────────────
info "Waiting for the app to be ready on port 8000..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health &>/dev/null; then
    log "App is healthy!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    warn "App health check timed out. Check logs with: docker compose logs app"
  fi
  sleep 3
done

# ─── Run DB migrations ────────────────────────────────────────────────────────
info "Running database migrations..."
docker compose exec -T app python -m alembic upgrade head
log "Migrations applied."

# ─── Seed initial data (only if tables are empty) ────────────────────────────
info "Seeding initial data..."
docker compose exec -T app python -m scripts.seed 2>/dev/null || warn "Seed already ran or skipped."

# ─── Start cloudflared tunnel ─────────────────────────────────────────────────
info "Starting public tunnel on port 8000..."

# Read the actual verify token from .env so the hint is always correct
VERIFY_TOKEN=$(grep -E "^META_VERIFY_TOKEN=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -z "$VERIFY_TOKEN" ]; then
  VERIFY_TOKEN="<see META_VERIFY_TOKEN in .env>"
fi

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Tunnel starting - look for a line like:              ${NC}"
echo -e "${YELLOW}  https://xxxx-xxxx.trycloudflare.com                  ${NC}"
echo -e "${YELLOW}                                                        ${NC}"
echo -e "${YELLOW}  Admin panel : <that-url>/                            ${NC}"
echo -e "${YELLOW}  Webhook URL : <that-url>/api/v1/webhook/instagram    ${NC}"
echo -e "${YELLOW}  Verify token: ${VERIFY_TOKEN}                        ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Start tunnel in background, capture the URL, then register the Meta webhook subscription
TUNNEL_LOG=$(mktemp)
cloudflared tunnel --url http://localhost:80 --protocol http2 2>&1 | tee "$TUNNEL_LOG" &
TUNNEL_PID=$!

# Wait for the public URL to appear
info "Waiting for tunnel URL..."
TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
  if [ -n "$TUNNEL_URL" ]; then break; fi
  sleep 2
done

if [ -n "$TUNNEL_URL" ]; then
  WEBHOOK_URL="${TUNNEL_URL}/api/v1/webhook/instagram"
  log "Tunnel URL: ${TUNNEL_URL}"

  # Read Meta credentials from .env
  APP_ID=$(grep -E "^META_APP_ID=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')
  APP_SECRET=$(grep -E "^META_APP_SECRET=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')
  VERIFY_TOKEN_VAL=$(grep -E "^META_VERIFY_TOKEN=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')

  if [ -n "$APP_ID" ] && [ -n "$APP_SECRET" ] && [ -n "$VERIFY_TOKEN_VAL" ]; then
    info "Registering webhook subscription with Meta..."
    APP_TOKEN=$(curl -sf "https://graph.facebook.com/oauth/access_token?client_id=${APP_ID}&client_secret=${APP_SECRET}&grant_type=client_credentials" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    if [ -n "$APP_TOKEN" ]; then
      RESULT=$(curl -sf -X POST "https://graph.facebook.com/v25.0/${APP_ID}/subscriptions" \
        -d "object=instagram" \
        -d "callback_url=${WEBHOOK_URL}" \
        -d "fields=comments,messages" \
        -d "verify_token=${VERIFY_TOKEN_VAL}" \
        -d "access_token=${APP_TOKEN}" 2>/dev/null)
      if echo "$RESULT" | grep -q '"success":true'; then
        log "Webhook subscription registered: comments + messages"
      else
        warn "Webhook subscription failed: $RESULT"
      fi
    else
      warn "Could not get app access token - register webhook manually"
    fi
  else
    warn "META_APP_ID/APP_SECRET/VERIFY_TOKEN not in .env - skipping auto-subscription"
  fi
fi

wait $TUNNEL_PID
