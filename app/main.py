from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import setup_logging, get_logger
from app.services.redis_client import get_redis, close_redis
from app.routers import webhook, products, promotions, prompts, faq, tickets, conversations, settings as settings_router, analytics
from app.routers import auth as auth_router

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("app_starting", environment=settings.environment)

    # Verify Redis connectivity
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("redis_connected")
    except Exception as exc:
        logger.error("redis_connection_failed", error=str(exc))

    yield

    # Shutdown
    await close_redis()
    logger.info("app_shutdown")


app = FastAPI(
    title="Instagram AI Sales Chatbot",
    description="Backend for lavender pillow e-commerce Instagram bot",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
API_PREFIX = "/api/v1"

app.include_router(auth_router.router, prefix=API_PREFIX)
app.include_router(webhook.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(promotions.router, prefix=API_PREFIX)
app.include_router(prompts.router, prefix=API_PREFIX)
app.include_router(faq.router, prefix=API_PREFIX)
app.include_router(tickets.router, prefix=API_PREFIX)
app.include_router(conversations.router, prefix=API_PREFIX)
app.include_router(settings_router.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
