# Warehouse Service

Два асинхронных сервиса для складских операций с обменом через Redis Streams.

- **inventory_api** — принимает поступления и расходы, публикует события, отдаёт остатки и сводки.
- **analytics_worker** — подписан на стримы, обновляет агрегированные остатки в БД.


## Стек

- Python 3.12
- aiohttp — веб-сервер
- SQLAlchemy Core (async) + asyncpg — доступ к PostgreSQL
- Alembic — миграции
- Redis Streams — транспорт между сервисами
- Pydantic v2 — валидация
- Docker Compose — окружение
- pytest + pytest-asyncio — тесты

## Запуск

Требуется Docker и Docker Compose.

```bash
git clone <repo>
cd warehouse-service
cp alembic/env.py.example alembic/env.py
docker compose up -d --build
```

Поднимутся четыре контейнера:

- `postgres` — основная БД `warehouse`
- `redis` — стримы и группы
- `api` — HTTP API на порту `8080`
- `worker` — консьюмер стримов

Миграции накатываются автоматически при старте `api`.

Проверка:

```bash
curl -i http://localhost:8080/stock?warehouse=WH-1
```

## API

### POST /receipts — поступление

```bash
curl -X POST http://localhost:8080/receipts \
  -H "Content-Type: application/json" \
  -d '{"sku":"A-100","qty":50,"warehouse":"WH-1"}'
```

Ответ `201 Created`:

```json
{
  "event_id": "6b1e...",
  "type": "receipt",
  "sku": "A-100",
  "qty": 50,
  "warehouse": "WH-1",
  "occurred_at": "2026-10-16T12:00:00+00:00"
}
```

### POST /issues — расход

```bash
curl -X POST http://localhost:8080/issues \
  -H "Content-Type: application/json" \
  -d '{"sku":"A-100","qty":20,"warehouse":"WH-1"}'
```

### GET /stock — остатки

```bash
curl "http://localhost:8080/stock?warehouse=WH-1"
curl "http://localhost:8080/stock?warehouse=WH-1&sku=A-100"
```

```json
[{"warehouse": "WH-1", "sku": "A-100", "qty": 30}]
```

### GET /stock/summary — сводка

```bash
curl "http://localhost:8080/stock/summary?top_n=5"
```

```json
{
  "warehouses": [
    {"warehouse": "WH-1", "total_qty": 130, "sku_count": 2},
    {"warehouse": "WH-2", "total_qty": 15, "sku_count": 2}
  ],
  "top_skus": [
    {"sku": "B-200", "total_qty": 100},
    {"sku": "A-100", "total_qty": 40},
    {"sku": "C-300", "total_qty": 5}
  ]
}
```

## Формат события

События публикуются в Redis Streams: `inventory.receipt`, `inventory.issue`.

```json
{
  "event_id": "uuid",
  "type": "receipt | issue",
  "sku": "A-100",
  "qty": 50,
  "warehouse": "WH-1",
  "occurred_at": "2026-10-16T12:00:00+00:00"
}
```

Каждая запись в стриме — одно поле `data` с этой JSON-строкой.

## Модель данных

### `stock_events`

Журнал операций. Только INSERT, растёт со временем.

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `type` | TEXT | `receipt` / `issue`, CHECK |
| `sku` | TEXT | |
| `qty` | INTEGER | CHECK > 0 |
| `warehouse` | TEXT | |
| `created_at` | TIMESTAMPTZ | server default now() |

Индексы: `(warehouse, sku)`, `(created_at)`.

### `stock_agg`

Агрегированный остаток. Одна строка на пару `(warehouse, sku)`.

| Колонка | Тип | Примечание |
|---|---|---|
| `warehouse` | TEXT | часть PK |
| `sku` | TEXT | часть PK |
| `qty` | INTEGER | может быть отрицательным |
| `updated_at` | TIMESTAMPTZ | |

Составной PK `(warehouse, sku)` даёт уникальность и используется в `ON CONFLICT` для UPSERT.

## Redis Streams

- **Публикация:** `XADD <stream> {"data": "<json>"} MAXLEN ~ 10000`.
- **Чтение:** consumer group `analytics_workers`, consumer `worker-1`, `XREADGROUP ... BLOCK 5000`.
- **Подтверждение:** `XACK` после успешного UPSERT.
- **Невалидные сообщения:** логируются и подтверждаются (чтобы не зацикливаться).
- **Ошибка БД:** сообщение остаётся в pending (PEL) и логируется.

## Тесты

```bash
docker compose run --rm api pytest
```

- Создают временную БД `warehouse_test` перед запуском и удаляют после.
- Используют отдельную Redis-базу (`/1`), чтобы не пересекаться с боевой (`/0`).
- Покрывают: валидацию API, запись в `stock_events` и стрим, UPSERT в `stock_agg`, обработку невалидных событий.
