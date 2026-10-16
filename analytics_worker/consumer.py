import asyncio
import logging

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db import stock_agg
from shared.events import CHANNELS, GROUP_NAME, StockEvent, parse_event


log = logging.getLogger(__name__)

CONSUMER_NAME = "worker-1"
BLOCK_MS = 5000
READ_COUNT = 10


def _delta(event: StockEvent) -> int:
    return event.qty if event.type == "receipt" else -event.qty


async def _ensure_group(redis: Redis) -> None:
    for channel in CHANNELS:
        try:
            await redis.xgroup_create(
                name=channel,
                groupname=GROUP_NAME,
                id="0",
                mkstream=True,
            )
            log.info("Создана группа %s для стрима %s", GROUP_NAME, channel)
        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                log.info("Группа %s уже существует для %s", GROUP_NAME, channel)
            else:
                raise


async def _apply_event(engine: AsyncEngine, event: StockEvent) -> None:
    delta = _delta(event)
    stmt = (
        pg_insert(stock_agg)
        .values(
            warehouse=event.warehouse,
            sku=event.sku,
            qty=delta,
            updated_at=func.now(),
        )
        .on_conflict_do_update(
            index_elements=[stock_agg.c.warehouse, stock_agg.c.sku],
            set_={
                "qty": stock_agg.c.qty + delta,
                "updated_at": func.now(),
            },
        )
    )
    async with engine.begin() as conn:
        await conn.execute(stmt)


async def _handle_message(
    engine: AsyncEngine,
    redis: Redis,
    channel: bytes,
    msg_id: bytes,
    fields: dict,
) -> None:
    raw = fields.get(b"data")
    if raw is None:
        log.warning("Нет поля `data` в сообщении %s on %s", msg_id, channel)
        await redis.xack(channel, GROUP_NAME, msg_id)
        return

    try:
        event = parse_event(raw)
    except ValidationError as e:
        log.warning(
            "Невалидное событие %s: %s | raw=%r",
            channel, e, raw,
        )
        await redis.xack(channel, GROUP_NAME, msg_id)
        return

    try:
        await _apply_event(engine, event)
    except Exception:
        log.exception(
            "Событие не применено %s (msg=%s); перенос в PEL",
            event.event_id, msg_id,
        )
        return

    await redis.xack(channel, GROUP_NAME, msg_id)
    log.info(
        "Применено %s sku=%s qty=%s warehouse=%s (msg=%s)",
        event.type, event.sku, event.qty, event.warehouse, msg_id,
    )


async def consume(engine: AsyncEngine, redis: Redis) -> None:
    await _ensure_group(redis)
    log.info(
        "Воркер %s слушает: %s",
        CONSUMER_NAME, ", ".join(CHANNELS),
    )

    streams = {channel: ">" for channel in CHANNELS}

    while True:
        try:
            result = await redis.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams=streams,
                count=READ_COUNT,
                block=BLOCK_MS,
            )
        except asyncio.CancelledError:
            log.info("Потребитель отключен, завершение работы")
            raise

        if not result:
            continue

        for channel, messages in result:
            for msg_id, fields in messages:
                await _handle_message(engine, redis, channel, msg_id, fields)


# async def  consume(engine: AsyncEngine, redis: Redis) -> None:
#     pubsub = redis.pubsub()
#     await pubsub.subscribe(*CHANNELS)
#     log.info("Подписаны на каналы: %s", ", ".join(CHANNELS))

#     try:
#         async for message in pubsub.listen():
#             if message["type"] != "message":
#                 # subscribe/unsubscribe-подтверждения — пропускаем
#                 continue

#             raw = message["data"]
#             try:
#                 event = parse_event(raw)
#             except ValidationError as e:
#                 log.warning("Невалидное событие %s: %s | raw=%r",
#                             message["channel"], e, raw)
#                 continue

#             try:
#                 await _apply_event(engine, event)
#                 log.info(
#                     "Применено %s sku=%s qty=%s warehouse=%s",
#                     event.type, event.sku, event.qty, event.warehouse,
#                 )
#             except Exception:
#                 log.exception("Ошибка применения события %s", event.event_id)
#     finally:
#         await pubsub.unsubscribe(*CHANNELS)
#         await pubsub.aclose()
#         log.info("Потребитель остановлен")
