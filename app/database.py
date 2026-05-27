import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings

# Celery workers call asyncio.run() for each task, creating a fresh event loop every time.
# A shared connection pool holds connections bound to the *previous* event loop, causing
# "another operation is in progress" errors on asyncpg.
# Solution: NullPool in worker processes — each DB call opens and closes its own connection,
# so there is no stale-loop mismatch.
_is_worker = os.environ.get("CELERY_WORKER", "false").lower() == "true"

_engine_kwargs: dict = {"echo": False}
if _is_worker:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
