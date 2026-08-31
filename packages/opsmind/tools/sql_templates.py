"""Allowlisted SQL templates — parameterized SELECT only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SqlTemplate:
    key: str
    description: str
    sql: str
    required_params: tuple[str, ...]
    allowlisted_tables: tuple[str, ...]


# Tables investigation tools may touch (business plane only — not memory tables).
ALLOWLISTED_TABLES: frozenset[str] = frozenset(
    {
        "products",
        "carriers",
        "campaigns",
        "orders",
        "order_items",
        "inventory_snapshots",
        "shipments",
        "returns",
        "daily_metrics",
    }
)

SQL_TEMPLATES: dict[str, SqlTemplate] = {
    "revenue_by_day": SqlTemplate(
        key="revenue_by_day",
        description="Daily revenue and order counts for a date window.",
        sql="""
            SELECT metric_date, revenue, orders_count, cancelled_orders,
                   units_sold, return_count, sla_breach_count
            FROM daily_metrics
            WHERE metric_date BETWEEN :start_date AND :end_date
            ORDER BY metric_date
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("daily_metrics",),
    ),
    "revenue_week_totals": SqlTemplate(
        key="revenue_week_totals",
        description="Aggregate revenue / orders / SLA breaches for a window.",
        sql="""
            SELECT
                MIN(metric_date) AS window_start,
                MAX(metric_date) AS window_end,
                ROUND(SUM(revenue)::numeric, 2) AS revenue,
                SUM(orders_count) AS orders_count,
                SUM(cancelled_orders) AS cancelled_orders,
                SUM(return_count) AS return_count,
                SUM(sla_breach_count) AS sla_breach_count
            FROM daily_metrics
            WHERE metric_date BETWEEN :start_date AND :end_date
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("daily_metrics",),
    ),
    "sku_revenue_mix": SqlTemplate(
        key="sku_revenue_mix",
        description="Revenue and units by SKU in a date window (completed orders).",
        sql="""
            SELECT p.sku, p.name,
                   ROUND(SUM(oi.line_total)::numeric, 2) AS revenue,
                   SUM(oi.quantity) AS units
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN products p ON p.id = oi.product_id
            WHERE o.order_date BETWEEN :start_date AND :end_date
              AND o.status = 'completed'
            GROUP BY p.sku, p.name
            ORDER BY revenue DESC
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("order_items", "orders", "products"),
    ),
    "inventory_by_sku": SqlTemplate(
        key="inventory_by_sku",
        description="Inventory snapshots for a SKU over a date window.",
        sql="""
            SELECT s.snapshot_date, p.sku, p.name, s.on_hand, s.reserved, s.available
            FROM inventory_snapshots s
            JOIN products p ON p.id = s.product_id
            WHERE p.sku = :sku
              AND s.snapshot_date BETWEEN :start_date AND :end_date
            ORDER BY s.snapshot_date
        """,
        required_params=("sku", "start_date", "end_date"),
        allowlisted_tables=("inventory_snapshots", "products"),
    ),
    "carrier_sla": SqlTemplate(
        key="carrier_sla",
        description="Shipment outcomes by carrier in a date window.",
        sql="""
            SELECT c.name AS carrier,
                   COUNT(*) AS shipments,
                   SUM(CASE WHEN sh.status = 'delivered_late' THEN 1 ELSE 0 END) AS late_count,
                   ROUND(AVG(sh.delay_hours)::numeric, 2) AS avg_delay_hours
            FROM shipments sh
            JOIN carriers c ON c.id = sh.carrier_id
            WHERE sh.ship_date BETWEEN :start_date AND :end_date
            GROUP BY c.name
            ORDER BY late_count DESC, shipments DESC
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("shipments", "carriers"),
    ),
    "campaign_activity": SqlTemplate(
        key="campaign_activity",
        description="Campaigns overlapping a date window.",
        sql="""
            SELECT name, channel, start_date, end_date, discount_pct, featured_sku, notes
            FROM campaigns
            WHERE start_date <= :end_date
              AND end_date >= :start_date
            ORDER BY start_date
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("campaigns",),
    ),
    "returns_by_reason": SqlTemplate(
        key="returns_by_reason",
        description="Returns grouped by reason and SKU in a date window.",
        sql="""
            SELECT r.reason, p.sku, p.name,
                   COUNT(*) AS return_count,
                   ROUND(SUM(r.refund_amount)::numeric, 2) AS refund_total
            FROM returns r
            JOIN order_items oi ON oi.id = r.order_item_id
            JOIN products p ON p.id = oi.product_id
            WHERE r.return_date BETWEEN :start_date AND :end_date
            GROUP BY r.reason, p.sku, p.name
            ORDER BY return_count DESC
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("returns", "order_items", "products"),
    ),
    "cancelled_orders": SqlTemplate(
        key="cancelled_orders",
        description="Cancelled order counts by day in a window.",
        sql="""
            SELECT order_date, COUNT(*) AS cancelled_count,
                   ROUND(SUM(net_amount)::numeric, 2) AS cancelled_net
            FROM orders
            WHERE order_date BETWEEN :start_date AND :end_date
              AND status = 'cancelled'
            GROUP BY order_date
            ORDER BY order_date
        """,
        required_params=("start_date", "end_date"),
        allowlisted_tables=("orders",),
    ),
}


FORBIDDEN_SQL_RE = (
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|CALL|EXECUTE|MERGE|REPLACE|UPSERT)\b"
)


def get_template(key: str) -> SqlTemplate:
    template = SQL_TEMPLATES.get(key)
    if template is None:
        known = ", ".join(sorted(SQL_TEMPLATES))
        raise KeyError(f"Unknown SQL template '{key}'. Allowlisted: {known}")
    return template


def list_templates() -> list[dict[str, str]]:
    return [
        {
            "key": t.key,
            "description": t.description,
            "required_params": ",".join(t.required_params),
        }
        for t in SQL_TEMPLATES.values()
    ]
