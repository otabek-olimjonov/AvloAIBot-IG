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

# ─── Skip cloudflared (using public domain) ───────────────────────────────────
info "Using public domain for incoming webhook (no tunnel)."

# ─── Start Docker services ────────────────────────────────────────────────────
info "Starting all services (this may take a few minutes on first run)..."
cd "$(dirname "$0")"
docker compose up -d --build
log "All Docker services started."

# Restart nginx after build so it re-resolves container IPs (prevents 502 from stale DNS cache)
docker compose restart nginx
log "nginx restarted (fresh DNS for upstream containers)."

# ─── Prepare ACME webroot and obtain certificates if needed ───────────────────
info "Ensuring ACME webroot exists and is writable..."
mkdir -p /var/www/certbot
chown -R $(id -u):$(id -g) /var/www/certbot || true

# Read certbot email from .env (optional)
CERTBOT_EMAIL=$(grep -E "^CERTBOT_EMAIL=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
# Domains to request
DOMAINS=("beekeeper.uz" "www.beekeeper.uz")

# Helper: join domains to -d args
domain_args=""
for d in "${DOMAINS[@]}"; do
  domain_args+=" -d $d"
done

# Only attempt to obtain certs if not already present
if [ ! -f /etc/letsencrypt/live/beekeeper.uz/fullchain.pem ]; then
  info "No existing certificate found for beekeeper.uz — attempting to obtain via Certbot webroot."
  if [ -n "$CERTBOT_EMAIL" ]; then
    CERT_EMAIL_ARG="--email $CERTBOT_EMAIL --agree-tos --no-eff-email"
  else
    warn "No CERTBOT_EMAIL set in .env — registering without email (not recommended)."
    CERT_EMAIL_ARG="--register-unsafely-without-email --agree-tos"
  fi

  set +e
  sudo certbot certonly --webroot -w /var/www/certbot $domain_args $CERT_EMAIL_ARG --non-interactive
  rc=$?
  set -e

  if [ $rc -eq 0 ]; then
    log "Certificates obtained successfully. Reloading nginx."
    docker compose exec nginx nginx -s reload || docker compose restart nginx
  else
    warn "Certbot failed (exit $rc). You may need to check DNS or run certbot manually."
  fi
else
  log "Existing certificate found for beekeeper.uz — skipping obtain step."
fi

# ─── Ensure automated renewal is scheduled (cron) ─────────────────────────────
info "Ensuring certbot renewal cron exists..."
CRON_ENTRY="0 3 * * * root certbot renew --post-hook 'docker compose exec nginx nginx -s reload' >> /var/log/letsencrypt/renew.log 2>&1"
if ! sudo grep -F "$CRON_ENTRY" /etc/crontab >/dev/null 2>&1; then
  sudo bash -c "echo '$CRON_ENTRY' >> /etc/crontab"
  log "Installed certbot renewal cron."
else
  log "Certbot renewal cron already present."
fi

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
# Read the actual verify token from .env so the hint is always correct
VERIFY_TOKEN=$(grep -E "^META_VERIFY_TOKEN=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')
if [ -z "$VERIFY_TOKEN" ]; then
  VERIFY_TOKEN="<see META_VERIFY_TOKEN in .env>"
fi

# Determine public URL for webhook registration. Preference order:
# 1) PUBLIC_URL in .env
# 2) VITE_API_URL in .env
# 3) default to https://beekeeper.uz
PUBLIC_URL=$(grep -E "^PUBLIC_URL=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -z "$PUBLIC_URL" ]; then
  PUBLIC_URL=$(grep -E "^VITE_API_URL=" .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
fi
if [ -z "$PUBLIC_URL" ]; then
  PUBLIC_URL="https://beekeeper.uz"
fi

WEBHOOK_URL="${PUBLIC_URL%/}/api/v1/webhook/instagram"
log "Using public webhook URL: ${WEBHOOK_URL}"

# Read Meta credentials from .env
APP_ID=$(grep -E "^META_APP_ID=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')
APP_SECRET=$(grep -E "^META_APP_SECRET=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')
VERIFY_TOKEN_VAL=$(grep -E "^META_VERIFY_TOKEN=" .env 2>/dev/null | cut -d= -f2- | tr -d '"')

if [ -n "$APP_ID" ] && [ -n "$APP_SECRET" ] && [ -n "$VERIFY_TOKEN_VAL" ]; then
  info "Registering webhook subscription with Meta using public domain..."
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
