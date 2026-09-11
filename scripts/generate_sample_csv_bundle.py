"""Generate the downloadable sample CSV ZIP bundle for new tenants to test with.

This is NOT the shared demo tenant's data (packages/opsmind/db/seed.py) — it's a
standalone, deterministic dataset shaped like the required upload format
(products.csv/orders.csv/order_items.csv + optional carriers/shipments/returns/
campaigns/inventory) with a few planted anomalies, so a brand-new tenant can
download it, upload it via Settings, and immediately have something interesting
to investigate without writing their own CSVs first.

Run:
    python -m scripts.generate_sample_csv_bundle

Regenerates data/sample_templates/opsmind_sample_data.zip deterministically
(fixed random seed) — safe to re-run any time the shape needs to change.
"""

from __future__ import annotations

import csv
import io
import random
import zipfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_templates"
OUT_ZIP = OUT_DIR / "opsmind_sample_data.zip"

# Fixed, explicit window — matches the same "problem week vs prior week" shape
# used by the seeded demo tenant, so ready-made example questions always work
# regardless of when someone actually uploads the file.
PRIOR_START = date(2026, 8, 3)
PRIOR_END = date(2026, 8, 9)
PROBLEM_START = date(2026, 8, 10)
PROBLEM_END = date(2026, 8, 16)

RNG = random.Random(20260810)  # deterministic output

PRODUCTS = [
    # sku, name, category, unit_price, unit_cost
    ("SAMPLE-1001", "Trailblazer Hiking Boots", "Footwear", "129.99", "58.00"),
    ("SAMPLE-1002", "AromaBrew Electric Kettle", "Home", "44.50", "19.00"),
    ("SAMPLE-1003", "Everyday Canvas Backpack", "Bags", "59.00", "24.00"),
    ("SAMPLE-1004", "FastCharge USB-C Cable 2m", "Electronics", "12.99", "3.50"),
    ("SAMPLE-1005", "CloudStep Running Socks (3-pack)", "Apparel", "18.00", "6.00"),
    ("SAMPLE-1006", "SunGuard Polarized Sunglasses", "Accessories", "34.00", "11.00"),
    ("SAMPLE-1007", "BaseCamp Insulated Bottle 1L", "Outdoor", "27.50", "9.50"),
    ("SAMPLE-1008", "NightOwl LED Desk Lamp", "Home", "39.99", "16.00"),
]

# Planted scenario drivers, mirroring the seeded demo tenant's playbook themes:
STOCKOUT_SKU = "SAMPLE-1001"     # goes to zero available stock in the problem week
RETURNS_SKU = "SAMPLE-1002"      # defective-seal return spike in the problem week
PROMO_SKU = "SAMPLE-1004"        # flash-sale discount overlapping the problem week
CARRIER_OK = "NorthPeak Freight"
CARRIER_LATE = "ValueLine Shipping"  # SLA breaches spike in the problem week

CHANNELS = ["web", "mobile_app", "marketplace"]
REGIONS = ["US-West", "US-East", "US-Central", "EU"]


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _write_csv(rows: list[dict], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def build() -> dict[str, bytes]:
    products_rows = [
        {
            "sku": sku,
            "name": name,
            "category": cat,
            "unit_price": price,
            "unit_cost": cost,
            "is_active": "true",
        }
        for sku, name, cat, price, cost in PRODUCTS
    ]

    carriers_rows = [
        {"name": CARRIER_OK, "sla_hours": "48"},
        {"name": CARRIER_LATE, "sla_hours": "48"},
    ]

    campaigns_rows = [
        {
            "name": "Charger Flash Sale",
            "channel": "web",
            "start_date": (PROBLEM_START + timedelta(days=1)).isoformat(),
            "end_date": (PROBLEM_START + timedelta(days=4)).isoformat(),
            "discount_pct": "30",
            "featured_sku": PROMO_SKU,
            "notes": "30% off FastCharge cables — sample cannibalization scenario",
        }
    ]

    orders_rows: list[dict] = []
    items_rows: list[dict] = []
    shipments_rows: list[dict] = []
    returns_rows: list[dict] = []
    inventory_rows: list[dict] = []

    order_seq = 0
    item_seq = 0

    def make_day_orders(day: date, *, is_problem_week: bool, base_orders: int) -> None:
        nonlocal order_seq, item_seq
        n_orders = base_orders
        if is_problem_week:
            # Overall softer day — plus the stockout SKU specifically stops selling.
            n_orders = max(1, int(base_orders * 0.8))

        for _ in range(n_orders):
            order_seq += 1
            order_id = f"S-{order_seq:05d}"
            status = "cancelled" if RNG.random() < 0.04 else "completed"
            channel = RNG.choice(CHANNELS)
            region = RNG.choice(REGIONS)

            # 1-3 line items per order, from products that aren't out of stock that day.
            available_skus = [
                p[0]
                for p in PRODUCTS
                if not (is_problem_week and p[0] == STOCKOUT_SKU and day >= PROBLEM_START + timedelta(days=2))
            ]
            n_items = RNG.randint(1, 3)
            chosen = RNG.sample(available_skus, k=min(n_items, len(available_skus)))

            gross = Decimal("0.00")
            order_item_refs: list[tuple[str, str]] = []
            for sku in chosen:
                product = next(p for p in PRODUCTS if p[0] == sku)
                unit_price = Decimal(product[3])
                if is_problem_week and sku == PROMO_SKU and PROBLEM_START + timedelta(days=1) <= day <= PROBLEM_START + timedelta(days=4):
                    unit_price = (unit_price * Decimal("0.70")).quantize(Decimal("0.01"))
                qty = RNG.randint(1, 3)
                line_total = (unit_price * qty).quantize(Decimal("0.01"))
                gross += line_total

                item_seq += 1
                items_rows.append(
                    {
                        "order_id": order_id,
                        "sku": sku,
                        "quantity": str(qty),
                        "unit_price": str(unit_price),
                        "line_total": str(line_total),
                    }
                )
                order_item_refs.append((sku, str(qty)))

            net = gross if status == "completed" else Decimal("0.00")
            orders_rows.append(
                {
                    "order_id": order_id,
                    "order_date": day.isoformat(),
                    "status": status,
                    "channel": channel,
                    "customer_region": region,
                    "gross_amount": str(gross),
                    "net_amount": str(net),
                }
            )

            if status != "cancelled":
                carrier = CARRIER_LATE if (is_problem_week and RNG.random() < 0.55) else CARRIER_OK
                ship_date = day + timedelta(days=1)
                promised = ship_date + timedelta(days=2)
                late = carrier == CARRIER_LATE and RNG.random() < 0.6
                delay_hours = RNG.randint(18, 40) if late else 0
                delivered = promised + timedelta(hours=delay_hours) if not late else promised + timedelta(days=1)
                shipments_rows.append(
                    {
                        "order_id": order_id,
                        "carrier_name": carrier,
                        "ship_date": ship_date.isoformat(),
                        "promised_date": promised.isoformat(),
                        "delivered_date": delivered.isoformat(),
                        "status": "delivered_late" if late else "delivered",
                        "delay_hours": str(delay_hours),
                        "sla_hours": "48",
                    }
                )

                # Returns spike on RETURNS_SKU in the problem week.
                for sku, qty in order_item_refs:
                    if sku == RETURNS_SKU and is_problem_week and RNG.random() < 0.35:
                        returns_rows.append(
                            {
                                "order_id": order_id,
                                "sku": sku,
                                "return_date": (day + timedelta(days=3)).isoformat(),
                                "reason": "defective_seal",
                                "refund_amount": str(
                                    (Decimal(next(p[3] for p in PRODUCTS if p[0] == sku)) * Decimal(qty)).quantize(
                                        Decimal("0.01")
                                    )
                                ),
                            }
                        )

    for day in _daterange(PRIOR_START, PRIOR_END):
        make_day_orders(day, is_problem_week=False, base_orders=14)
    for day in _daterange(PROBLEM_START, PROBLEM_END):
        make_day_orders(day, is_problem_week=True, base_orders=14)

    # Inventory snapshots — daily, per product. STOCKOUT_SKU craters mid problem-week.
    for day in _daterange(PRIOR_START, PROBLEM_END):
        for sku, *_ in PRODUCTS:
            on_hand = RNG.randint(40, 120)
            if sku == STOCKOUT_SKU and day >= PROBLEM_START + timedelta(days=2):
                on_hand = 0
            reserved = min(on_hand, RNG.randint(0, 10))
            available = max(0, on_hand - reserved)
            inventory_rows.append(
                {
                    "snapshot_date": day.isoformat(),
                    "sku": sku,
                    "on_hand": str(on_hand),
                    "reserved": str(reserved),
                    "available": str(available),
                }
            )

    return {
        "products.csv": _write_csv(
            products_rows, ["sku", "name", "category", "unit_price", "unit_cost", "is_active"]
        ),
        "orders.csv": _write_csv(
            orders_rows,
            [
                "order_id",
                "order_date",
                "status",
                "channel",
                "customer_region",
                "gross_amount",
                "net_amount",
            ],
        ),
        "order_items.csv": _write_csv(
            items_rows, ["order_id", "sku", "quantity", "unit_price", "line_total"]
        ),
        "carriers.csv": _write_csv(carriers_rows, ["name", "sla_hours"]),
        "campaigns.csv": _write_csv(
            campaigns_rows,
            ["name", "channel", "start_date", "end_date", "discount_pct", "featured_sku", "notes"],
        ),
        "inventory.csv": _write_csv(
            inventory_rows, ["snapshot_date", "sku", "on_hand", "reserved", "available"]
        ),
        "shipments.csv": _write_csv(
            shipments_rows,
            [
                "order_id",
                "carrier_name",
                "ship_date",
                "promised_date",
                "delivered_date",
                "status",
                "delay_hours",
                "sla_hours",
            ],
        ),
        "returns.csv": _write_csv(
            returns_rows, ["order_id", "sku", "return_date", "reason", "refund_amount"]
        ),
    }


def main() -> None:
    files = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    total_rows = sum(content.count(b"\n") - 1 for content in files.values())
    print(f"[generate_sample_csv_bundle] wrote {OUT_ZIP} ({total_rows} data rows across {len(files)} files)")
    print(f"[generate_sample_csv_bundle] prior week:   {PRIOR_START} .. {PRIOR_END}")
    print(f"[generate_sample_csv_bundle] problem week: {PROBLEM_START} .. {PROBLEM_END}")


if __name__ == "__main__":
    main()
