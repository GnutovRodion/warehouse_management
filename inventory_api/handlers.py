import json

from aiohttp import web
from pydantic import ValidationError
from sqlalchemy import insert, select, func, desc

from inventory_api.schemas import OperationRequest
from shared.db import stock_events, stock_agg
from shared.events import StockEvent, CHANNEL_BY_TYPE, dump_event


async def _parse_body(request: web.Request) -> OperationRequest:
    try:
        raw = await request.json()
    except json.JSONDecodeError:
        raise web.HTTPBadRequest(text="Невалидный JSON")
    try:
        return OperationRequest.model_validate(raw)
    except ValidationError as e:
        raise web.HTTPBadRequest(text=e.json(), content_type="application/json")


async def _record_operation(
    request: web.Request,
    op_type: str,
    payload: OperationRequest,
) -> StockEvent:
    engine = request.app["engine"]
    redis = request.app["redis"]

    event = StockEvent(
        type=op_type,
        sku=payload.sku,
        qty=payload.qty,
        warehouse=payload.warehouse,
    )

    async with engine.begin() as conn:
        await conn.execute(
            insert(stock_events).values(
                type=event.type,
                sku=event.sku,
                qty=event.qty,
                warehouse=event.warehouse,
            )
        )

    # await redis.publish(CHANNEL_BY_TYPE[event.type], dump_event(event))
    await redis.xadd(
        CHANNEL_BY_TYPE[event.type],
        {"data": dump_event(event)},
        maxlen=10000,
    )
    return event


async def create_receipt(request: web.Request) -> web.Response:
    payload = await _parse_body(request)
    event = await _record_operation(request, "receipt", payload)
    return web.json_response(event.model_dump(mode="json"), status=201)


async def create_issue(request: web.Request) -> web.Response:
    payload = await _parse_body(request)
    event = await _record_operation(request, "issue", payload)
    return web.json_response(event.model_dump(mode="json"), status=201)


async def get_stock(request: web.Request) -> web.Response:
    warehouse = request.query.get("warehouse")
    if not warehouse:
        raise web.HTTPBadRequest(text="Необходимо передать warehouse")

    sku = request.query.get("sku")
    query = select(
        stock_agg.c.warehouse, stock_agg.c.sku, stock_agg.c.qty
    ).where(stock_agg.c.warehouse == warehouse)
    if sku:
        query = query.where(stock_agg.c.sku == sku)
    query = query.order_by(stock_agg.c.sku)

    engine = request.app["engine"]
    async with engine.connect() as conn:
        rows = (await conn.execute(query)).mappings().all()
    return web.json_response([dict(r) for r in rows])


async def get_stock_summary(request: web.Request) -> web.Response:
    try:
        top_n = int(request.query.get("top_n", 5))
    except ValueError:
        raise web.HTTPBadRequest(text="top_n должен быть целым числом")
    if top_n <= 0:
        raise web.HTTPBadRequest(text="top_n должен быть положительным числом")
    top_n = min(top_n, 100)

    engine = request.app["engine"]

    per_warehouse = (
        select(
            stock_agg.c.warehouse,
            func.sum(stock_agg.c.qty).label("total_qty"),
            func.count(func.distinct(stock_agg.c.sku)).label("sku_count"),
        )
        .group_by(stock_agg.c.warehouse)
        .order_by(stock_agg.c.warehouse)
    )

    per_sku = (
        select(
            stock_agg.c.sku,
            func.sum(stock_agg.c.qty).label("total_qty"),
        )
        .group_by(stock_agg.c.sku)
        .subquery()
    )
    top_skus = (
        select(per_sku.c.sku, per_sku.c.total_qty)
        .order_by(desc(per_sku.c.total_qty))
        .limit(top_n)
    )

    async with engine.connect() as conn:
        wh_rows = (await conn.execute(per_warehouse)).mappings().all()
        sku_rows = (await conn.execute(top_skus)).mappings().all()

    return web.json_response({
        "warehouses": [dict(r) for r in wh_rows],
        "top_skus": [dict(r) for r in sku_rows],
    })
