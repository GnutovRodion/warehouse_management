import json

import pytest
from sqlalchemy import select

from shared.db import stock_events
from shared.events import CHANNEL_RECEIPT, CHANNEL_ISSUE


async def test_create_receipt_writes_event_and_stream(
    api_client, test_engine, test_redis
):
    resp = await api_client.post(
        "/receipts",
        json={"sku": "T1-A", "qty": 50, "warehouse": "T1-WH"},
    )
    assert resp.status == 201
    body = await resp.json()
    assert body["type"] == "receipt"
    assert body["sku"] == "T1-A"
    assert body["qty"] == 50

    async with test_engine.connect() as conn:
        rows = (await conn.execute(
            select(stock_events).where(stock_events.c.sku == "T1-A")
        )).mappings().all()
    assert len(rows) == 1
    assert rows[0]["qty"] == 50

    length = await test_redis.xlen(CHANNEL_RECEIPT)
    assert length == 1
    entries = await test_redis.xrange(CHANNEL_RECEIPT)
    _, fields = entries[0]
    payload = json.loads(fields[b"data"])
    assert payload["sku"] == "T1-A"


async def test_create_issue_writes_event(api_client, test_engine, test_redis):
    resp = await api_client.post(
        "/issues",
        json={"sku": "T2-A", "qty": 10, "warehouse": "T2-WH"},
    )
    assert resp.status == 201
    body = await resp.json()
    assert body["type"] == "issue"

    async with test_engine.connect() as conn:
        rows = (await conn.execute(
            select(stock_events).where(stock_events.c.sku == "T2-A")
        )).mappings().all()
    assert len(rows) == 1
    assert rows[0]["type"] == "issue"

    assert await test_redis.xlen(CHANNEL_ISSUE) == 1


@pytest.mark.parametrize("payload", [
    {"sku": "", "qty": 5, "warehouse": "WH"},
    {"sku": "A", "qty": 0, "warehouse": "WH"},
    {"sku": "A", "qty": -5, "warehouse": "WH"},
    {"sku": "A", "qty": 5, "warehouse": ""},
    {"sku": "A", "qty": 5},          # нет warehouse
])
async def test_receipt_validation_errors(api_client, payload):
    resp = await api_client.post("/receipts", json=payload)
    assert resp.status == 400


async def test_receipt_invalid_json(api_client):
    resp = await api_client.post(
        "/receipts",
        data="{not json}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_stock_requires_warehouse(api_client):
    resp = await api_client.get("/stock")
    assert resp.status == 400


async def test_stock_summary_bad_top_n(api_client):
    resp = await api_client.get("/stock/summary?top_n=abc")
    assert resp.status == 400
    resp = await api_client.get("/stock/summary?top_n=0")
    assert resp.status == 400
