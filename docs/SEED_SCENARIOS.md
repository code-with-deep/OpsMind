# Seed calendar & planted failure modes (Phase 1)

Synthetic ecommerce/warehouse data is **deterministic** (`random.seed(42)`).
Re-running the seed truncates business tables and reloads the same world.

## Calendar

| Window | Dates |
|--------|-------|
| Full seed range | **2026-07-06 → 2026-08-23** (~7 weeks) |
| Prior (healthy) week | **2026-08-10 → 2026-08-16** |
| Problem week | **2026-08-17 → 2026-08-23** |

Primary demo question:

> Why did our revenue decrease this week (**2026-08-17 to 2026-08-23**), and what should we do?

Compare against prior week **2026-08-10 to 2026-08-16**.

## Catalog highlights

| SKU | Product | Role in story |
|-----|---------|----------------|
| `SKU-1001` | Wireless Earbuds Pro | Top seller → **stockout** in problem week |
| `SKU-1002` | Smart Water Bottle | **Return spike** (defective_seal) |
| `SKU-1004` | USB-C Cable 3-Pack | **Flash-sale cannibalization** target |
| — | FastShip Express | Carrier with **SLA breaches** in problem week |

## Planted failure modes (problem week)

### 1. Stockout — Wireless Earbuds Pro (`SKU-1001`)
- Inventory drains; from **2026-08-19** available stock is **0**
- More cancellations / lost earbuds revenue
- Visible in `inventory_snapshots` + cancelled `orders`

### 2. Carrier SLA breaches — FastShip Express
- Elevated late deliveries (`shipments.status = delivered_late`, higher `delay_hours`)
- Visible in `shipments` joined to `carriers`, and `daily_metrics.sla_breach_count`

### 3. Promo cannibalization — Cable Flash Sale
- Campaign: **PROBLEM: Cable Flash Sale** (paid_social, 40% off `SKU-1004`)
- Cable volume surges; earbuds share softens even before full stockout
- Visible in `campaigns` + `order_items` mix by SKU

### 4. Returns spike — Smart Water Bottle (`SKU-1002`)
- Higher return rate with reason `defective_seal`
- Visible in `returns`

## Tables

`products`, `carriers`, `campaigns`, `orders`, `order_items`, `inventory_snapshots`, `shipments`, `returns`, `daily_metrics`

## Read-only DB role

Seed creates/updates role from env:

- `DB_READONLY_USER`
- `DB_READONLY_PASSWORD`

Grants: `CONNECT` + `USAGE` on `public` + `SELECT` on all tables (and default privileges for future tables).

Investigation tools (P2+) must use the read-only URL, not the owner account.

## How to (re)seed

```powershell
docker compose exec api alembic upgrade head
docker compose exec api python -m opsmind.db.seed
```
