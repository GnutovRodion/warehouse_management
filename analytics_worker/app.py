import logging
import os

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from analytics_worker.consumer import consume


log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://warehouse:warehouse@localhost:5432/warehouse",
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def run_worker() -> None:
    engine: AsyncEngine = create_async_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    redis: Redis = Redis.from_url(
        REDIS_URL,
        decode_responses=False,
        socket_timeout=30,
    )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await redis.ping()
        log.info("Подключение к postgres и redis выполнено")

        await consume(engine, redis)
    finally:
        await engine.dispose()
        await redis.aclose()
        log.info("Завершение работы воркера")
