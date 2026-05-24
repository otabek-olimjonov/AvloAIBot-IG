# Instagram AI Sales Chatbot — Backend

Python/FastAPI backend for the AvloAI lavender pillow Instagram chatbot. Handles DMs and comments, guides customers through a 7-stage sales funnel, verifies payment screenshots via Gemini Vision, and dispatches order tickets to a Telegram operator group.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn + Gunicorn |
| DB | PostgreSQL 16 |
| Cache / Queue | Redis 7 + Celery |
| AI | Google Gemini 2.5 Flash |
| Instagram | Meta Graph API v21 |
| Telegram | aiogram 3.x |
| Deploy | Docker Compose + Nginx |

---

## Quick start (local development)

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd Instagram_Chatbot

# 2. Copy env file and fill in values
cp .env.example .env
# Edit .env with your API keys

# 3. Start all services
docker compose up --build

# 4. Run migrations
docker compose exec app python -m alembic upgrade head

# 5. Seed initial data
docker compose exec app python -m scripts.seed
```

API docs available at `http://localhost/docs`

---

## Deployment on Contabo VPS (Ubuntu 24.04)

### 1. Initial server setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose (v2)
sudo apt install docker-compose-plugin -y

# Install Nginx and Certbot
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 2. Deploy the application

```bash
# Clone the repository
git clone <repo-url> /opt/instagram_bot
cd /opt/instagram_bot

# Configure environment
cp .env.example .env
nano .env  # Fill in all values

# Update nginx.conf with your domain
sed -i 's/your-domain.com/yourdomain.com/g' nginx/nginx.conf
```

### 3. Obtain SSL certificate

```bash
# Stop nginx if running
sudo systemctl stop nginx

# Get certificate (replace with your domain)
sudo certbot certonly --standalone -d yourdomain.com

# Auto-renewal cron
echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -
```

### 4. Start the stack

```bash
cd /opt/instagram_bot
docker compose up -d --build

# Run database migrations
docker compose exec app python -m alembic upgrade head

# Seed initial data
docker compose exec app python -m scripts.seed

# Check all services are healthy
docker compose ps
```

### 5. Configure Meta Webhook

In Meta Developer Console:
- Webhook URL: `https://yourdomain.com/api/v1/webhook/instagram`
- Verify token: value from `META_VERIFY_TOKEN` in your `.env`
- Subscribe to: `messages`, `messaging_postbacks`, `feed`

### 6. Verify

```bash
# Health check
curl https://yourdomain.com/health

# Test Telegram integration
curl -X POST https://yourdomain.com/api/v1/settings/test-telegram \
  -H "X-API-Key: your_api_key"
```

---

## Environment variables

See `.env.example` for all required variables with documentation.

Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL async URL |
| `REDIS_URL` | Redis connection URL |
| `GEMINI_API_KEY` | Google Gemini API key |
| `META_APP_SECRET` | Meta app secret for signature verification |
| `META_ACCESS_TOKEN` | Instagram Page Access Token |
| `META_VERIFY_TOKEN` | Custom token for webhook verification |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_GROUP_ID` | Telegram group chat ID (negative number) |
| `API_SECRET_KEY` | Admin panel API key (`X-API-Key` header) |
| `CORS_ORIGINS` | Comma-separated allowed origins for admin panel |

---

## Database migrations

```bash
# Apply all migrations
docker compose exec app python -m alembic upgrade head

# Create a new migration after model changes
docker compose exec app python -m alembic revision --autogenerate -m "description"

# Rollback last migration
docker compose exec app python -m alembic downgrade -1
```

---

## Project structure

```
app/
├── main.py              # FastAPI app + lifespan
├── config.py            # Settings (pydantic-settings)
├── database.py          # Async SQLAlchemy engine
├── celery_app.py        # Celery configuration
├── logging_config.py    # Structured JSON logging
├── models/              # SQLAlchemy ORM models (8 tables)
├── schemas/             # Pydantic request/response models
├── routers/             # FastAPI route handlers
│   ├── webhook.py       # Instagram webhook (GET verify + POST events)
│   ├── products.py      # CRUD
│   ├── promotions.py    # CRUD
│   ├── prompts.py       # GET + PUT
│   ├── faq.py           # CRUD
│   ├── tickets.py       # Read-only + paginated
│   ├── conversations.py # Read-only + messages
│   ├── settings.py      # Batch GET/PUT + test-telegram
│   └── analytics.py     # Dashboard, chart, products breakdown
├── services/
│   ├── auth.py          # X-API-Key middleware
│   ├── instagram.py     # Meta Graph API client
│   ├── ai_engine.py     # Gemini text generation + prompt builder
│   ├── vision.py        # Gemini Vision payment screenshot analysis
│   ├── telegram.py      # aiogram bot + ticket formatting + callbacks
│   └── redis_client.py  # Async Redis client
└── tasks/
    └── message_processing.py  # Celery task: full DM processing pipeline

alembic/
└── versions/
    └── 0001_initial_schema.py  # All 8 tables

scripts/
└── seed.py              # Initial products, prompts, settings

nginx/
└── nginx.conf           # SSL termination + rate limiting
```

---

## API endpoints

Full interactive docs at `/docs` (Swagger UI).

| Method | Endpoint | Auth |
|---|---|---|
| GET | `/api/v1/webhook/instagram` | Public (Meta challenge) |
| POST | `/api/v1/webhook/instagram` | Signature-verified |
| GET/POST/PUT/DELETE | `/api/v1/products` | X-API-Key |
| GET/POST/PUT/DELETE | `/api/v1/promotions` | X-API-Key |
| GET/PUT | `/api/v1/prompts` | X-API-Key |
| GET/POST/PUT/DELETE | `/api/v1/faq` | X-API-Key |
| GET | `/api/v1/tickets` | X-API-Key |
| GET | `/api/v1/conversations` | X-API-Key |
| GET/PUT | `/api/v1/settings` | X-API-Key |
| POST | `/api/v1/settings/test-telegram` | X-API-Key |
| GET | `/api/v1/analytics/dashboard` | X-API-Key |
| GET | `/api/v1/analytics/chart` | X-API-Key |
| GET | `/api/v1/analytics/products` | X-API-Key |

---

## Logs

All logs are structured JSON. To view:

```bash
docker compose logs -f app
docker compose logs -f worker
```
