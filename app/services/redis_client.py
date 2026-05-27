import os
import redis.asyncio as aioredis
from app.config import settings

_redis_client: aioredis.Redis | None = None

# Celery workers call asyncio.run() per task, creating a fresh event loop every time.
# A cached Redis client holds a TCP connection bound to the *previous* event loop,
# causing "TCPTransport closed" errors. In worker mode we always create a fresh client.
_is_worker = os.environ.get("CELERY_WORKER", "false").lower() == "true"


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _is_worker:
        # Never cache across event loops in Celery workers
        return aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
