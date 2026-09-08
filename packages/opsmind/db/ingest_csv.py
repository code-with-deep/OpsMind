"""CSV → ecommerce schema ingest for a single tenant (MT4)."""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

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

REQUIRED_FILES = ("products.csv", "orders.csv", "order_items.csv")
OPTIONAL_FILES = (
    "carriers.csv",
    "shipments.csv",
    "returns.csv",
    "campaigns.csv",
    "inventory.csv",
)
KNOWN_FILES = set(REQUIRED_FILES) | set(OPTIONAL_FILES)

_SERIAL_TABLES = (
    "products",
    "carriers",
    "campaigns",
    "orders",
    "order_items",
    "inventory_snapshots",
    "shipments",
    "returns",
)


class CsvIngestError(ValueError):
    """Validation / mapping failure for tenant CSV uploads."""


@dataclass
class IngestResult:
    row_counts: dict[str, int] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


def _parse_bool(raw: str | None, default: bool = True) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "t"}


def _parse_date(raw: str, field_name: str) -> date:
    value = (raw or "").strip()
    if not value:
        raise CsvIngestError(f"{field_name} is required")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise CsvIngestError(f"Invalid date for {field_name}: {raw!r}") from exc


def _parse_decimal(raw: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(raw).strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError) as exc:
        raise CsvIngestError(f"Invalid number for {field_name}: {raw!r}") from exc


def _parse_int(raw: str, field_name: str, default: int | None = None) -> int:
    text_value = (raw or "").strip()
    if not text_value:
        if default is not None:
            return default
        raise CsvIngestError(f"{field_name} is required")
    try:
        return int(text_value)
    except ValueError as exc:
        raise CsvIngestError(f"Invalid integer for {field_name}: {raw!r}") from exc


def _read_csv_rows(content: bytes, filename: str) -> list[dict[str, str]]:
    try:
        text_value = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvIngestError(f"{filename} must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text_value))
    if not reader.fieldnames:
        raise CsvIngestError(f"{filename} has no header row")
    rows: list[dict[str, str]] = []
    for idx, row in enumerate(reader, start=2):
        cleaned = {
            (k or "").strip().lower(): (v or "").strip()
            for k, v in row.items()
            if k is not None
        }
        if not any(cleaned.values()):
            continue
        cleaned["_line"] = str(idx)
        rows.append(cleaned)
    return rows


def _require_cols(row: dict[str, str], cols: tuple[str, ...], filename: str) -> None:
    missing = [c for c in cols if not row.get(c)]
    if missing:
        raise CsvIngestError(
            f"{filename} line {row.get('_line', '?')}: missing columns {missing}"
        )


def extract_csv_bundle(payload: bytes, filename: str) -> dict[str, bytes]:
    """Accept a .zip of named CSVs or a single products/orders/order_items file name."""
    name = (filename or "").lower()
    if name.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                out: dict[str, bytes] = {}
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    base = info.filename.split("/")[-1].lower()
                    if base in KNOWN_FILES:
                        out[base] = zf.read(info)
                return out
        except zipfile.BadZipFile as exc:
            raise CsvIngestError("Invalid ZIP archive") from exc

    base = name.split("/")[-1]
    if base in KNOWN_FILES:
        return {base: payload}
    raise CsvIngestError(
        "Upload a ZIP containing products.csv, orders.csv, order_items.csv "
        "(optional: carriers, shipments, returns, campaigns, inventory)"
    )


def clear_tenant_business_data(session: Session, tenant_id: UUID) -> None:
    """Delete only this tenant's ecommerce rows (safe for re-upload)."""
    # Child → parent order
    for model in (
        Return,
        Shipment,
        InventorySnapshot,
        OrderItem,
        Order,
        Campaign,
        Carrier,
        Product,
        DailyMetric,
    ):
        session.execute(delete(model).where(model.tenant_id == tenant_id))
    session.flush()


def _sync_id_sequences(session: Session) -> None:
    """Keep SERIAL sequences above existing demo/seed rows (global integer PKs)."""
    for table in _SERIAL_TABLES:
        session.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(:table_name, 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                    false
                )
                """
            ),
            {"table_name": f"public.{table}"},
        )
    session.flush()


def tenant_data_ready(session: Session, tenant_id: UUID) -> dict[str, Any]:
    """Ready-gate: CSV data in OpsMind tables."""
    products = session.scalar(
        select(func.count()).select_from(Product).where(Product.tenant_id == tenant_id)
    ) or 0
    orders = session.scalar(
        select(func.count()).select_from(Order).where(Order.tenant_id == tenant_id)
    ) or 0
    metrics = session.scalar(
        select(func.count()).select_from(DailyMetric).where(DailyMetric.tenant_id == tenant_id)
    ) or 0
    ready = int(products) > 0 and int(orders) > 0 and int(metrics) > 0
    return {
        "ready": ready,
        "products": int(products),
        "orders": int(orders),
        "daily_metrics": int(metrics),
    }


def _derive_daily_metrics(session: Session, tenant_id: UUID) -> int:
    session.execute(delete(DailyMetric).where(DailyMetric.tenant_id == tenant_id))

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

    orders = session.scalars(select(Order).where(Order.tenant_id == tenant_id)).all()
    items = session.scalars(select(OrderItem).where(OrderItem.tenant_id == tenant_id)).all()
    shipments = session.scalars(select(Shipment).where(Shipment.tenant_id == tenant_id)).all()
    returns = session.scalars(select(Return).where(Return.tenant_id == tenant_id)).all()

    items_by_order: dict[int, list[OrderItem]] = defaultdict(list)
    for item in items:
        items_by_order[item.order_id].append(item)

    for order in orders:
        d = order.order_date
        day_stats[d]["orders"] += 1
        if order.status == "cancelled":
            day_stats[d]["cancelled"] += 1
        else:
            day_stats[d]["revenue"] += order.net_amount
            day_stats[d]["units"] += sum(i.quantity for i in items_by_order.get(order.id, []))

    for ship in shipments:
        order = next((o for o in orders if o.id == ship.order_id), None)
        d = order.order_date if order else ship.ship_date
        day_stats[d]["fulfill_hours"].append(float(ship.delay_hours))
        if ship.delay_hours > 0 or ship.status in {"delivered_late", "delayed"}:
            day_stats[d]["sla_breaches"] += 1

    for ret in returns:
        day_stats[ret.return_date]["returns"] += 1

    count = 0
    for d, stats in sorted(day_stats.items()):
        fulfill = stats["fulfill_hours"]
        avg_f = (
            Decimal(str(round(sum(fulfill) / len(fulfill), 2)))
            if fulfill
            else Decimal("0.00")
        )
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
        count += 1
    session.flush()
    return count


def ingest_csv_tables(
    session: Session,
    *,
    tenant_id: UUID,
    files: dict[str, bytes],
    max_rows: int,
    replace: bool = True,
) -> IngestResult:
    missing = [name for name in REQUIRED_FILES if name not in files]
    if missing:
        raise CsvIngestError(f"Missing required files: {', '.join(missing)}")

    total_rows = 0
    parsed: dict[str, list[dict[str, str]]] = {}
    for name, raw in files.items():
        if name not in KNOWN_FILES:
            continue
        rows = _read_csv_rows(raw, name)
        total_rows += len(rows)
        if total_rows > max_rows:
            raise CsvIngestError(f"CSV soft limit exceeded ({max_rows} rows)")
        parsed[name] = rows

    if replace:
        clear_tenant_business_data(session, tenant_id)

    _sync_id_sequences(session)

    counts: dict[str, int] = {}

    # products
    sku_to_product: dict[str, Product] = {}
    for row in parsed["products.csv"]:
        _require_cols(
            row,
            ("sku", "name", "category", "unit_price", "unit_cost"),
            "products.csv",
        )
        sku = row["sku"]
        if sku in sku_to_product:
            raise CsvIngestError(f"Duplicate sku in products.csv: {sku}")
        product = Product(
            tenant_id=tenant_id,
            sku=sku,
            name=row["name"],
            category=row["category"],
            unit_price=_parse_decimal(row["unit_price"], "unit_price"),
            unit_cost=_parse_decimal(row["unit_cost"], "unit_cost"),
            is_active=_parse_bool(row.get("is_active"), True),
        )
        session.add(product)
        sku_to_product[sku] = product
    session.flush()
    counts["products"] = len(sku_to_product)

    # carriers (optional)
    carrier_by_name: dict[str, Carrier] = {}
    for row in parsed.get("carriers.csv", []):
        _require_cols(row, ("name", "sla_hours"), "carriers.csv")
        carrier = Carrier(
            tenant_id=tenant_id,
            name=row["name"],
            sla_hours=_parse_int(row["sla_hours"], "sla_hours"),
        )
        session.add(carrier)
        carrier_by_name[row["name"]] = carrier
    session.flush()
    counts["carriers"] = len(carrier_by_name)

    # campaigns (optional)
    campaigns = 0
    for row in parsed.get("campaigns.csv", []):
        _require_cols(
            row,
            ("name", "channel", "start_date", "end_date", "discount_pct"),
            "campaigns.csv",
        )
        session.add(
            Campaign(
                tenant_id=tenant_id,
                name=row["name"],
                channel=row["channel"],
                start_date=_parse_date(row["start_date"], "start_date"),
                end_date=_parse_date(row["end_date"], "end_date"),
                discount_pct=_parse_decimal(row["discount_pct"], "discount_pct"),
                featured_sku=row.get("featured_sku") or None,
                notes=row.get("notes") or None,
            )
        )
        campaigns += 1
    counts["campaigns"] = campaigns

    # orders — external order_id → db id
    external_to_order_id: dict[str, int] = {}
    for row in parsed["orders.csv"]:
        _require_cols(
            row,
            (
                "order_id",
                "order_date",
                "status",
                "channel",
                "customer_region",
                "gross_amount",
                "net_amount",
            ),
            "orders.csv",
        )
        ext = row["order_id"]
        if ext in external_to_order_id:
            raise CsvIngestError(f"Duplicate order_id in orders.csv: {ext}")
        order = Order(
            tenant_id=tenant_id,
            order_date=_parse_date(row["order_date"], "order_date"),
            status=row["status"],
            channel=row["channel"],
            customer_region=row["customer_region"],
            gross_amount=_parse_decimal(row["gross_amount"], "gross_amount"),
            net_amount=_parse_decimal(row["net_amount"], "net_amount"),
        )
        session.add(order)
        session.flush()
        external_to_order_id[ext] = order.id
    counts["orders"] = len(external_to_order_id)

    # order_items
    item_key_to_id: dict[tuple[str, str], int] = {}
    items_n = 0
    for row in parsed["order_items.csv"]:
        _require_cols(
            row,
            ("order_id", "sku", "quantity", "unit_price", "line_total"),
            "order_items.csv",
        )
        ext = row["order_id"]
        sku = row["sku"]
        if ext not in external_to_order_id:
            raise CsvIngestError(f"order_items.csv unknown order_id={ext}")
        if sku not in sku_to_product:
            raise CsvIngestError(f"order_items.csv unknown sku={sku}")
        item = OrderItem(
            tenant_id=tenant_id,
            order_id=external_to_order_id[ext],
            product_id=sku_to_product[sku].id,
            quantity=_parse_int(row["quantity"], "quantity"),
            unit_price=_parse_decimal(row["unit_price"], "unit_price"),
            line_total=_parse_decimal(row["line_total"], "line_total"),
        )
        session.add(item)
        session.flush()
        item_key_to_id[(ext, sku)] = item.id
        items_n += 1
    counts["order_items"] = items_n

    # inventory (optional)
    inv_n = 0
    for row in parsed.get("inventory.csv", []):
        _require_cols(
            row,
            ("snapshot_date", "sku", "on_hand", "reserved", "available"),
            "inventory.csv",
        )
        sku = row["sku"]
        if sku not in sku_to_product:
            raise CsvIngestError(f"inventory.csv unknown sku={sku}")
        session.add(
            InventorySnapshot(
                tenant_id=tenant_id,
                snapshot_date=_parse_date(row["snapshot_date"], "snapshot_date"),
                product_id=sku_to_product[sku].id,
                on_hand=_parse_int(row["on_hand"], "on_hand"),
                reserved=_parse_int(row["reserved"], "reserved"),
                available=_parse_int(row["available"], "available"),
            )
        )
        inv_n += 1
    counts["inventory"] = inv_n

    # shipments (optional) — auto-create carriers by name if needed
    ship_n = 0
    for row in parsed.get("shipments.csv", []):
        _require_cols(
            row,
            (
                "order_id",
                "carrier_name",
                "ship_date",
                "promised_date",
                "status",
            ),
            "shipments.csv",
        )
        ext = row["order_id"]
        if ext not in external_to_order_id:
            raise CsvIngestError(f"shipments.csv unknown order_id={ext}")
        cname = row["carrier_name"]
        if cname not in carrier_by_name:
            carrier = Carrier(
                tenant_id=tenant_id,
                name=cname,
                sla_hours=_parse_int(row.get("sla_hours", ""), "sla_hours", default=48),
            )
            session.add(carrier)
            session.flush()
            carrier_by_name[cname] = carrier
        delivered_raw = row.get("delivered_date") or ""
        session.add(
            Shipment(
                tenant_id=tenant_id,
                order_id=external_to_order_id[ext],
                carrier_id=carrier_by_name[cname].id,
                ship_date=_parse_date(row["ship_date"], "ship_date"),
                promised_date=_parse_date(row["promised_date"], "promised_date"),
                delivered_date=_parse_date(delivered_raw, "delivered_date")
                if delivered_raw
                else None,
                status=row["status"],
                delay_hours=_parse_int(row.get("delay_hours", ""), "delay_hours", default=0),
            )
        )
        ship_n += 1
    counts["shipments"] = ship_n
    counts["carriers"] = len(carrier_by_name)

    # returns (optional)
    ret_n = 0
    for row in parsed.get("returns.csv", []):
        _require_cols(
            row,
            ("order_id", "sku", "return_date", "reason", "refund_amount"),
            "returns.csv",
        )
        ext = row["order_id"]
        sku = row["sku"]
        key = (ext, sku)
        if key not in item_key_to_id:
            raise CsvIngestError(
                f"returns.csv no order_item for order_id={ext} sku={sku}"
            )
        session.add(
            Return(
                tenant_id=tenant_id,
                order_id=external_to_order_id[ext],
                order_item_id=item_key_to_id[key],
                return_date=_parse_date(row["return_date"], "return_date"),
                reason=row["reason"],
                refund_amount=_parse_decimal(row["refund_amount"], "refund_amount"),
            )
        )
        ret_n += 1
    counts["returns"] = ret_n

    counts["daily_metrics"] = _derive_daily_metrics(session, tenant_id)
    session.flush()
    return IngestResult(row_counts=counts, files=sorted(parsed.keys()))


def sample_bundle_bytes() -> bytes:
    """Minimal valid ZIP for docs/tests."""
    products = (
        "sku,name,category,unit_price,unit_cost,is_active\n"
        "SKU-A,Alpha Widget,Widgets,40.00,12.00,true\n"
        "SKU-B,Beta Gadget,Gadgets,25.00,8.00,true\n"
    )
    orders = (
        "order_id,order_date,status,channel,customer_region,gross_amount,net_amount\n"
        "O-1,2026-08-18,completed,web,West,40.00,40.00\n"
        "O-2,2026-08-19,completed,mobile,East,50.00,50.00\n"
        "O-3,2026-08-19,cancelled,web,West,25.00,0.00\n"
        "O-4,2026-08-20,completed,web,Central,80.00,80.00\n"
    )
    items = (
        "order_id,sku,quantity,unit_price,line_total\n"
        "O-1,SKU-A,1,40.00,40.00\n"
        "O-2,SKU-A,1,40.00,40.00\n"
        "O-2,SKU-B,1,10.00,10.00\n"
        "O-3,SKU-B,1,25.00,25.00\n"
        "O-4,SKU-A,2,40.00,80.00\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("products.csv", products)
        zf.writestr("orders.csv", orders)
        zf.writestr("order_items.csv", items)
    return buf.getvalue()
