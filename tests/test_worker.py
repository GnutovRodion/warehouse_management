from sqlalchemy import select

from analytics_worker.consumer import _apply_event
from shared.db import stock_agg
from shared.events import StockEvent


async def _fetch_qty(engine, warehouse: str, sku: str) -> int | None:
    async with engine.connect() as conn:
        row = (await conn.execute(
            select(stock_agg.c.qty).where(
                stock_agg.c.warehouse == warehouse,
                stock_agg.c.sku == sku,
            )
        )).first()
    return row[0] if row else None


async def test_receipt_upserts_stock(test_engine):
    event = StockEvent(type="receipt", sku="W1-A", qty=50, warehouse="W1-WH")
    await _apply_event(test_engine, event)
    assert await _fetch_qty(test_engine, "W1-WH", "W1-A") == 50


async def test_issue_decreases_stock(test_engine):
    e1 = StockEvent(type="receipt", sku="W2-A", qty=100, warehouse="W2-WH")
    e2 = StockEvent(type="issue", sku="W2-A", qty=30, warehouse="W2-WH")
    await _apply_event(test_engine, e1)
    await _apply_event(test_engine, e2)
    assert await _fetch_qty(test_engine, "W2-WH", "W2-A") == 70


async def test_issue_can_go_negative(test_engine):
    event = StockEvent(type="issue", sku="W3-A", qty=10, warehouse="W3-WH")
    await _apply_event(test_engine, event)
    assert await _fetch_qty(test_engine, "W3-WH", "W3-A") == -10


async def test_upsert_updates_existing_row(test_engine):
    for _ in range(3):
        await _apply_event(
            test_engine,
            StockEvent(type="receipt", sku="W4-A", qty=10, warehouse="W4-WH"),
        )
    async with test_engine.connect() as conn:
        rows = (await conn.execute(
            select(stock_agg).where(stock_agg.c.warehouse == "W4-WH")
        )).mappings().all()
    assert len(rows) == 1
    assert rows[0]["qty"] == 30
