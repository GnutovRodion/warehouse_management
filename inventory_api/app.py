import os

from aiohttp import web
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


DATABASE_URL = os.environ.get(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://warehouse:warehouse@localhost:5432/warehouse",
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def on_startup(app: web.Application) -> None:
    engine: AsyncEngine = create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    app["engine"] = engine

    redis: Redis = Redis.from_url(
        REDIS_URL,
        decode_responses=False,
        socket_timeout=30,
    )
    app["redis"] = redis

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await redis.ping()


async def on_cleanup(app: web.Application) -> None:
    await app["engine"].dispose()
    await app["redis"].aclose()


def create_app(*, engine: AsyncEngine = None, redis: Redis = None) -> web.Application:
    app = web.Application()

    if engine is not None and redis is not None:
        app["engine"] = engine
        app["redis"] = redis
    else:
        app.on_startup.append(on_startup)
        app.on_cleanup.append(on_cleanup)

    from inventory_api.routes import setup_routes
    setup_routes(app)

    return app
