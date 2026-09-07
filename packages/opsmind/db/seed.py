"""Deterministic synthetic ecommerce/warehouse seed with planted failure modes.

Run inside API container or local venv:

    python -m opsmind.db.seed

Idempotent: truncates business tables then reloads.
"""

from __future__ import annotations

import os
import random
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from opsmind.db.models import (
    Campaign,
    Carrier,
    DailyMetric,
    InventorySnapshot,
    Order,
    OrderItem,
    Product,
    Return,
    Shipment,
)
from opsmind.db import tenant_models as _tenant_models  # noqa: F401 — register tenants FK targets

# Fixed calendar so demos/evals are stable across machines.
SEED_START = date(2026, 7, 6)  # Monday
SEED_END = date(2026, 8, 23)  # Sunday
PROBLEM_WEEK_START = date(2026, 8, 17)
PROBLEM_WEEK_END = date(2026, 8, 23)
PRIOR_WEEK_START = date(2026, 8, 10)
PRIOR_WEEK_END = date(2026, 8, 16)

TOP_SKU = "SKU-1001"  # Wireless Earbuds Pro — stockout victim
PROMO_SKU = "SKU-1004"  # Cable Pack — flash-sale cannibalization
RETURN_SKU = "SKU-1002"  # Smart Bottle — quality return spike
FASTSHIP = "FastShip Express"

# Fixed demo tenant id — must match Alembic 0007_multi_tenant_core.
DEMO_TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def _require_sync_url() -> str:
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("DATABASE_URL_SYNC must be set via environment /.env")
    return url


def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _is_problem_week(d: date) -> bool:
    return PROBLEM_WEEK_START <= d <= PROBLEM_WEEK_END


def ensure_readonly_role(engine: Engine) -> None:
    """Create/update read-only login used by investigation tools (P2+)."""
    user = os.getenv("DB_READONLY_USER")
    password = os.getenv("DB_READONLY_PASSWORD")
    if not user or password is None:
        user = "opsmind_readonly"
        password = "opsmind_readonly"

    # Role DDL cannot run inside an aborted transaction cleanly with ORM session.
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            curr_user = conn.execute(text("SELECT current_user")).scalar()
            if curr_user == user:
                # Connected as same user (e.g. cloud db owner), skip role creation/alteration
                return

            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :u"),
                {"u": user},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE ROLE "{user}" LOGIN PASSWORD :pw'), {"pw": password})
            else:
                conn.execute(text(f'ALTER ROLE "{user}" WITH LOGIN PASSWORD :pw'), {"pw": password})

            db_name = engine.url.database
            if db_name:
                conn.execute(text(f'GRANT CONNECT ON DATABASE "{db_name}" TO "{user}"'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{user}"'))
            conn.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{user}"'))
            conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    f'GRANT SELECT ON TABLES TO "{user}"'
                )
            )
    except Exception as exc:
        # On managed cloud databases (Neon, AWS RDS, Supabase), role DDL is restricted.
        # Allow seeding and ingestion to proceed gracefully.
        print(f"Notice: Skipped read-only role DDL ({exc}). Proceeding.")


def clear_business_data(session: Session) -> None:
    for table in (
        "returns",
        "shipments",
        "inventory_snapshots",
        "order_items",
        "orders",
        "daily_metrics",
        "campaigns",
        "carriers",
        "products",
    ):
        session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    session.commit()


def seed_products(session: Session, tenant_id: uuid.UUID) -> dict[str, Product]:
    catalog = [
        (TOP_SKU, "Wireless Earbuds Pro", "Audio", "129.00", "45.00"),
        (RETURN_SKU, "Smart Water Bottle", "Lifestyle", "49.00", "18.00"),
        ("SKU-1003", "Desk Lamp Elite", "Home", "79.00", "28.00"),
        (PROMO_SKU, "USB-C Cable 3-Pack", "Accessories", "19.00", "4.00"),
        ("SKU-1005", "Laptop Stand Aluminum", "Office", "59.00", "22.00"),
        ("SKU-1006", "Noise Cancelling Headphones", "Audio", "199.00", "70.00"),
        ("SKU-1007", "Portable Charger 20k", "Accessories", "39.00", "12.00"),
        ("SKU-1008", "Ergo Mouse", "Office", "45.00", "15.00"),
    ]
    products: dict[str, Product] = {}
    for sku, name, category, price, cost in catalog:
        p = Product(
            tenant_id=tenant_id,
            sku=sku,
            name=name,
            category=category,
            unit_price=Decimal(price),
            unit_cost=Decimal(cost),
            is_active=True,
        )
        session.add(p)
        products[sku] = p
    session.flush()
    return products


def seed_carriers(session: Session, tenant_id: uuid.UUID) -> dict[str, Carrier]:
    carriers = {
        FASTSHIP: Carrier(tenant_id=tenant_id, name=FASTSHIP, sla_hours=48),
        "Regional Freight": Carrier(tenant_id=tenant_id, name="Regional Freight", sla_hours=72),
        "Economy Parcel": Carrier(tenant_id=tenant_id, name="Economy Parcel", sla_hours=120),
    }
    session.add_all(carriers.values())
    session.flush()
    return carriers


def seed_campaigns(session: Session, tenant_id: uuid.UUID) -> None:
    session.add_all(
        [
            Campaign(
                tenant_id=tenant_id,
                name="Summer Steady — Email",
                channel="email",
                start_date=date(2026, 7, 10),
                end_date=date(2026, 7, 20),
                discount_pct=Decimal("10.00"),
                featured_sku="SKU-1006",
                notes="Healthy promo; no major distortion.",
            ),
            Campaign(
                tenant_id=tenant_id,
                name="PROBLEM: Cable Flash Sale",
                channel="paid_social",
                start_date=PROBLEM_WEEK_START,
                end_date=PROBLEM_WEEK_END,
                discount_pct=Decimal("40.00"),
                featured_sku=PROMO_SKU,
                notes=(
                    "Planted cannibalization: deep discount on Cable Pack diverted "
                    "demand from Wireless Earbuds Pro during the problem week."
                ),
            ),
        ]
    )


def _base_daily_orders(d: date) -> int:
    # Weekdays higher than weekends.
    base = 42 if d.weekday() < 5 else 28
    if _is_problem_week(d):
        return max(18, int(base * 0.62))
    return base + random.randint(-3, 3)


def _sku_weights(d: date, stockout_active: bool) -> list[tuple[str, float]]:
    weights = {
        TOP_SKU: 0.28,
        RETURN_SKU: 0.12,
        "SKU-1003": 0.10,
        PROMO_SKU: 0.08,
        "SKU-1005": 0.10,
        "SKU-1006": 0.14,
        "SKU-1007": 0.10,
        "SKU-1008": 0.08,
    }
    if _is_problem_week(d):
        # Promo cannibalization: cables surge, earbuds demand softens even before stockout.
        weights[PROMO_SKU] = 0.30
        weights[TOP_SKU] = 0.12
        if stockout_active:
            weights[TOP_SKU] = 0.02
    total = sum(weights.values())
    return [(sku, w / total) for sku, w in weights.items()]


def _pick_sku(weights: list[tuple[str, float]]) -> str:
    skus, ws = zip(*weights)
    return random.choices(list(skus), weights=list(ws), k=1)[0]


def seed_orders_and_ops(
    session: Session,
    tenant_id: uuid.UUID,
    products: dict[str, Product],
    carriers: dict[str, Carrier],
) -> None:
    inventory = {sku: 800 for sku in products}
    inventory[TOP_SKU] = 2500

    order_id_seq = 1
    item_id_seq = 1
    shipment_id_seq = 1
    return_id_seq = 1

    # Collect rows for daily_metrics
    day_stats: dict[date, dict[str, Any]] = defaultdict(
        lambda: {
            "revenue": Decimal("0"),
            "orders": 0,
            "cancelled": 0,
            "units": 0,
            "returns": 0,
            "fulfill_hours": [],
            "sla_breaches": 0,
        }
    )

    regions = ["West", "East", "Central", "South"]
    channels = ["web", "mobile", "marketplace"]

    for d in _daterange(SEED_START, SEED_END):
        # Stockout of top SKU from Wed of problem week onward.
        stockout_active = _is_problem_week(d) and d >= date(2026, 8, 19)
        if stockout_active:
            inventory[TOP_SKU] = 0

        # Inventory snapshot at start of day
        for sku, on_hand in inventory.items():
            reserved = min(on_hand, random.randint(5, 40))
            available = max(0, on_hand - reserved)
            session.add(
                InventorySnapshot(
                    tenant_id=tenant_id,
                    snapshot_date=d,
                    product_id=products[sku].id,
                    on_hand=on_hand,
                    reserved=reserved,
                    available=available,
                )
            )

        n_orders = _base_daily_orders(d)
        weights = _sku_weights(d, stockout_active=stockout_active)

        for _ in range(n_orders):
            status = "completed"
            # Cancellations rise in problem week when stockout hits.
            if stockout_active and random.random() < 0.18:
                status = "cancelled"
            elif random.random() < 0.03:
                status = "cancelled"

            sku = _pick_sku(weights)
            product = products[sku]
            qty = 1 if random.random() < 0.7 else 2

            # If top SKU stockout and somehow selected, cancel or substitute cables.
            if sku == TOP_SKU and stockout_active:
                if random.random() < 0.7:
                    status = "cancelled"
                else:
                    sku = PROMO_SKU
                    product = products[sku]

            unit_price = product.unit_price
            if _is_problem_week(d) and sku == PROMO_SKU:
                unit_price = (unit_price * Decimal("0.60")).quantize(Decimal("0.01"))

            line_total = (unit_price * qty).quantize(Decimal("0.01"))
            gross = line_total
            net = Decimal("0.00") if status == "cancelled" else line_total

            order = Order(
                id=order_id_seq,
                tenant_id=tenant_id,
                order_date=d,
                status=status,
                channel=random.choice(channels),
                customer_region=random.choice(regions),
                gross_amount=gross,
                net_amount=net,
                created_at=datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
            )
            session.add(order)

            item = OrderItem(
                id=item_id_seq,
                tenant_id=tenant_id,
                order_id=order_id_seq,
                product_id=product.id,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
            session.add(item)

            day_stats[d]["orders"] += 1
            if status == "cancelled":
                day_stats[d]["cancelled"] += 1
            else:
                day_stats[d]["revenue"] += net
                day_stats[d]["units"] += qty
                if inventory[sku] > 0:
                    inventory[sku] = max(0, inventory[sku] - qty)

                # Shipments
                carrier_name = FASTSHIP if random.random() < 0.55 else random.choice(
                    ["Regional Freight", "Economy Parcel"]
                )
                carrier = carriers[carrier_name]
                ship_date = d
                promised_date = ship_date + timedelta(days=max(1, carrier.sla_hours // 24))

                delay_hours = 0
                delivered = promised_date
                ship_status = "delivered"
                if _is_problem_week(d) and carrier_name == FASTSHIP and random.random() < 0.55:
                    delay_hours = random.randint(24, 72)
                    delivered = promised_date + timedelta(days=max(1, delay_hours // 24))
                    ship_status = "delivered_late"
                    day_stats[d]["sla_breaches"] += 1
                elif random.random() < 0.06:
                    delay_hours = random.randint(6, 30)
                    delivered = promised_date + timedelta(days=1)
                    ship_status = "delivered_late"
                    day_stats[d]["sla_breaches"] += 1

                session.add(
                    Shipment(
                        id=shipment_id_seq,
                        tenant_id=tenant_id,
                        order_id=order_id_seq,
                        carrier_id=carrier.id,
                        ship_date=ship_date,
                        promised_date=promised_date,
                        delivered_date=delivered,
                        status=ship_status,
                        delay_hours=delay_hours,
                    )
                )
                day_stats[d]["fulfill_hours"].append(
                    float(carrier.sla_hours + delay_hours)
                )
                shipment_id_seq += 1

                # Returns: elevated for Smart Bottle in problem week
                return_chance = 0.04
                if _is_problem_week(d) and sku == RETURN_SKU:
                    return_chance = 0.28
                if random.random() < return_chance:
                    reason = (
                        "defective_seal"
                        if sku == RETURN_SKU and _is_problem_week(d)
                        else random.choice(["changed_mind", "damaged_in_transit", "wrong_item"])
                    )
                    refund = line_total
                    session.add(
                        Return(
                            id=return_id_seq,
                            tenant_id=tenant_id,
                            order_id=order_id_seq,
                            order_item_id=item_id_seq,
                            return_date=min(SEED_END, d + timedelta(days=random.randint(1, 5))),
                            reason=reason,
                            refund_amount=refund,
                        )
                    )
                    day_stats[d]["returns"] += 1
                    # Net revenue impact approximated on return day metrics later via count;
                    # refunds reduce problem-week economics via separate reporting.
                    return_id_seq += 1

            order_id_seq += 1
            item_id_seq += 1

        # Drain remaining top-SKU inventory into stockout by Wed of problem week
        if d == date(2026, 8, 18):
            inventory[TOP_SKU] = min(inventory[TOP_SKU], 15)
        if d >= date(2026, 8, 19) and d <= PROBLEM_WEEK_END:
            inventory[TOP_SKU] = 0

    for d, stats in day_stats.items():
        fulfill = stats["fulfill_hours"]
        avg_f = Decimal(str(round(sum(fulfill) / len(fulfill), 2))) if fulfill else Decimal("0")
        session.add(
            DailyMetric(
                tenant_id=tenant_id,
                metric_date=d,
                revenue=stats["revenue"].quantize(Decimal("0.01")),
                orders_count=stats["orders"],
                cancelled_orders=stats["cancelled"],
                units_sold=stats["units"],
                return_count=stats["returns"],
                avg_fulfillment_hours=avg_f,
                sla_breach_count=stats["sla_breaches"],
            )
        )


def _resolve_demo_tenant_id(session: Session) -> uuid.UUID:
    row = session.execute(
        text("SELECT id FROM tenants WHERE slug = 'demo' LIMIT 1")
    ).scalar()
    if row is not None:
        return uuid.UUID(str(row))
    return DEMO_TENANT_ID


def run_seed() -> None:
    random.seed(42)
    engine = create_engine(_require_sync_url(), future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as session:
        tenant_id = _resolve_demo_tenant_id(session)
        clear_business_data(session)
        products = seed_products(session, tenant_id)
        carriers = seed_carriers(session, tenant_id)
        seed_campaigns(session, tenant_id)
        seed_orders_and_ops(session, tenant_id, products, carriers)
        session.commit()

    ensure_readonly_role(engine)

    # Print verification summary for operators
    with SessionLocal() as session:
        tenant_id = _resolve_demo_tenant_id(session)
        prior = session.execute(
            text(
                """
                SELECT COALESCE(SUM(revenue),0)
                FROM daily_metrics
                WHERE tenant_id = :tenant_id AND metric_date BETWEEN :a AND :b
                """
            ),
            {"tenant_id": str(tenant_id), "a": PRIOR_WEEK_START, "b": PRIOR_WEEK_END},
        ).scalar()
        problem = session.execute(
            text(
                """
                SELECT COALESCE(SUM(revenue),0)
                FROM daily_metrics
                WHERE tenant_id = :tenant_id AND metric_date BETWEEN :a AND :b
                """
            ),
            {"tenant_id": str(tenant_id), "a": PROBLEM_WEEK_START, "b": PROBLEM_WEEK_END},
        ).scalar()
        print("Seed complete.")
        print(f"Prior week  ({PRIOR_WEEK_START} -> {PRIOR_WEEK_END}): revenue={prior}")
        print(f"Problem week({PROBLEM_WEEK_START} -> {PROBLEM_WEEK_END}): revenue={problem}")
        if prior and problem is not None and Decimal(str(prior)) > 0:
            drop_pct = (Decimal(str(prior)) - Decimal(str(problem))) / Decimal(str(prior)) * 100
            print(f"Revenue change: {drop_pct.quantize(Decimal('0.1'))}%")


def main() -> None:
    run_seed()


if __name__ == "__main__":
    main()
