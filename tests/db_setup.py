import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from shared.db import metadata


ADMIN_URL = os.environ.get(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://warehouse:warehouse@localhost:5432/warehouse",
)

TEST_DB_NAME = "warehouse_test"

TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"


async def create_test_database() -> AsyncEngine:
    admin_engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await admin_engine.dispose()

    test_engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with test_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    return test_engine


async def drop_test_database(test_engine: AsyncEngine) -> None:
    await test_engine.dispose()
    admin_engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin_engine.dispose()
