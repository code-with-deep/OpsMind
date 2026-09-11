# Sample CSV + playbook bundles

Two ready-made, deterministic bundles for trying OpsMind against **your own
tenant** without writing CSVs/SOPs by hand first. Both are separate from the
shared public demo tenant ("Try Live Demo") — they upload into *your*
company's workspace, so they're private to you. Download both from
**Settings** (Business data section, and Playbooks section).

- `opsmind_sample_data.zip` — CSV business data. Upload via **Settings →
  Business data → Upload CSV ZIP**.
  Regenerate: `python -m scripts.generate_sample_csv_bundle` (deterministic,
  fixed seed — same output every run).
- `opsmind_sample_playbooks.zip` — 5 SOP Markdown files (`playbooks/*.md`),
  tuned to reference the exact SKUs/carriers in the CSV bundle above. Upload
  the ZIP as-is via **Settings → Playbooks → Upload SOP(s)** — ZIP uploads
  are extracted server-side and every `.md`/`.markdown`/`.txt` file inside is
  ingested individually.
  Regenerate: `python -m scripts.generate_sample_playbooks_bundle`.

Upload the CSV bundle first, then the playbooks, so investigations can cite
both SQL evidence and matching SOP guidance.

## What's inside

| File | Required? | Rows |
|---|---|---|
| `products.csv` | yes | 8 |
| `orders.csv` | yes | ~175 |
| `order_items.csv` | yes | ~350 |
| `carriers.csv` | optional | 2 |
| `campaigns.csv` | optional | 1 |
| `inventory.csv` | optional | ~110 |
| `shipments.csv` | optional | ~170 |
| `returns.csv` | optional | ~12 |

## The planted scenario

Two weeks of orders — a normal **prior week** (`2026-08-03` to `2026-08-09`)
and a **problem week** (`2026-08-10` to `2026-08-16`) with three overlapping,
realistic drivers behind a **~39% revenue drop**:

- **Stockout** — `SAMPLE-1001` (Trailblazer Hiking Boots) runs out of available
  inventory for the back half of the problem week.
- **Carrier SLA breach** — `ValueLine Shipping` racks up late deliveries in the
  problem week (vs. the on-time `NorthPeak Freight`).
- **Returns spike** — `SAMPLE-1002` (AromaBrew Electric Kettle) gets a run of
  `defective_seal` returns in the problem week.
- (Minor) a 30%-off flash sale on `SAMPLE-1004` overlaps the problem week too,
  for a cannibalization-flavored red herring.

## Try these questions after uploading

- *"Why did revenue decrease in the week of 2026-08-10 compared to the prior week?"*
- *"Did we have a stockout on SAMPLE-1001 in August 2026?"*
- *"Which carrier had delivery delays between 2026-08-10 and 2026-08-16?"*
- *"Why did returns spike for SAMPLE-1002 with defective_seal reason codes?"*
