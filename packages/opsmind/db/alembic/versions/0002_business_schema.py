"""Business schema for ecommerce/warehouse domain.

Revision ID: 0002_business_schema
Revises: 0001_baseline
Create Date: 2026-08-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_business_schema"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.create_table(
        "carriers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sla_hours", sa.Integer(), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("featured_sku", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("customer_region", sa.String(length=64), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_orders_order_date", "orders", ["order_date"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.UniqueConstraint("snapshot_date", "product_id", name="uq_inventory_day_product"),
    )
    op.create_index("ix_inventory_snapshots_snapshot_date", "inventory_snapshots", ["snapshot_date"])
    op.create_index("ix_inventory_snapshots_product_id", "inventory_snapshots", ["product_id"])

    op.create_table(
        "shipments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("carrier_id", sa.Integer(), sa.ForeignKey("carriers.id"), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=False),
        sa.Column("promised_date", sa.Date(), nullable=False),
        sa.Column("delivered_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("delay_hours", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"])
    op.create_index("ix_shipments_carrier_id", "shipments", ["carrier_id"])
    op.create_index("ix_shipments_ship_date", "shipments", ["ship_date"])

    op.create_table(
        "returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id"), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_returns_order_id", "returns", ["order_id"])
    op.create_index("ix_returns_order_item_id", "returns", ["order_item_id"])
    op.create_index("ix_returns_return_date", "returns", ["return_date"])

    op.create_table(
        "daily_metrics",
        sa.Column("metric_date", sa.Date(), primary_key=True),
        sa.Column("revenue", sa.Numeric(14, 2), nullable=False),
        sa.Column("orders_count", sa.Integer(), nullable=False),
        sa.Column("cancelled_orders", sa.Integer(), nullable=False),
        sa.Column("units_sold", sa.Integer(), nullable=False),
        sa.Column("return_count", sa.Integer(), nullable=False),
        sa.Column("avg_fulfillment_hours", sa.Numeric(8, 2), nullable=False),
        sa.Column("sla_breach_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("daily_metrics")
    op.drop_table("returns")
    op.drop_table("shipments")
    op.drop_table("inventory_snapshots")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("campaigns")
    op.drop_table("carriers")
    op.drop_table("products")
