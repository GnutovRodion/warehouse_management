from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


MAX_STREAM_LEN = 10_000
GROUP_NAME = "analytics_workers"

CHANNEL_RECEIPT = "inventory.receipt"
CHANNEL_ISSUE = "inventory.issue"

CHANNEL_BY_TYPE: dict[str, str] = {
    "receipt": CHANNEL_RECEIPT,
    "issue": CHANNEL_ISSUE,
}

CHANNELS: list[str] = [CHANNEL_RECEIPT, CHANNEL_ISSUE]


class StockEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    type: Literal["receipt", "issue"]
    sku: str = Field(min_length=1, max_length=100)
    qty: int = Field(gt=0)
    warehouse: str = Field(min_length=1, max_length=100)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def dump_event(event: StockEvent) -> str:
    return event.model_dump_json()


def parse_event(raw: str | bytes) -> StockEvent:
    return StockEvent.model_validate_json(raw)
