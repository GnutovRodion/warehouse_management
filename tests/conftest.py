import os

import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from inventory_api.app import create_app
from tests.db_setup import create_test_database, drop_test_database


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncEngine:
    engine = await create_test_database()
    yield engine
    await drop_test_database(engine)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_redis() -> Redis:
    url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    test_url = url.rsplit("/", 1)[0] + "/1"
    client = Redis.from_url(test_url, decode_responses=False)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def api_client(test_engine, test_redis):
    app = create_app(engine=test_engine, redis=test_redis)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()
