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
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Tunnel starting — look for a line like:              ${NC}"
echo -e "${YELLOW}  https://xxxx-xxxx.trycloudflare.com                  ${NC}"
echo -e "${YELLOW}                                                        ${NC}"
echo -e "${YELLOW}  Copy that URL and paste it into Claude as:            ${NC}"
echo -e "${YELLOW}  Webhook URL: <that-url>/api/v1/webhook/instagram      ${NC}"
echo -e "${YELLOW}  Verify token: fc13fb44381927ce2cfc225ad0849ebb470eede5${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cloudflared tunnel --url http://localhost:8000
