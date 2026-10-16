from sqlalchemy import (BigInteger, CheckConstraint, Column, DateTime, Index,
                        Integer, MetaData, Table, Text, func)


metadata = MetaData()

stock_events = Table(
    "stock_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("type", Text, nullable=False),
    Column("sku", Text, nullable=False),
    Column("qty", Integer, nullable=False),
    Column("warehouse", Text, nullable=False),
    Column("created_at", DateTime(timezone=True),
           server_default=func.now(), nullable=False),
    CheckConstraint("type IN ('receipt', 'issue')", name="ck_stock_events_type"),
    CheckConstraint("qty > 0", name="ck_stock_events_qty_positive"),
)

Index("ix_stock_events_warehouse_sku", stock_events.c.warehouse, stock_events.c.sku)
Index("ix_stock_events_created_at", stock_events.c.created_at)


stock_agg = Table(
    "stock_agg",
    metadata,
    Column("warehouse", Text, primary_key=True),
    Column("sku", Text, primary_key=True),
    Column("qty", Integer, nullable=False, server_default="0"),
    Column("updated_at", DateTime(timezone=True),
           server_default=func.now(), nullable=False),
)
