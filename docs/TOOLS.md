# OpsMind Phase 2 — Tools & Evidence

Allowlisted SQL + playbook RAG tools that return structured **Evidence** and
persist every call to `tool_invocations` / `findings`.

## Demo without agents

```powershell
# After migrate + seed + playbook ingest (see README)
curl http://localhost:8000/tools/sql/templates

curl -X POST http://localhost:8000/tools/dates/normalize `
  -H "Content-Type: application/json" `
  -d "{\"expression\":\"problem_week\"}"

curl -X POST http://localhost:8000/tools/sql/run `
  -H "Content-Type: application/json" `
  -d "{\"template_key\":\"revenue_week_totals\",\"params\":{\"start_date\":\"2026-08-17\",\"end_date\":\"2026-08-23\"}}"

curl -X POST http://localhost:8000/tools/rag/query `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"stockout escalation\"}"
```

## SQL templates

| Key | Purpose |
|-----|---------|
| `revenue_by_day` | Daily metrics window |
| `revenue_week_totals` | Aggregate revenue / SLA / returns |
| `sku_revenue_mix` | Completed-order revenue by SKU |
| `inventory_by_sku` | Inventory snapshots for one SKU |
| `carrier_sla` | Late shipments by carrier |
| `campaign_activity` | Campaigns overlapping a window |
| `returns_by_reason` | Returns by reason + SKU |
| `cancelled_orders` | Cancelled order counts by day |

All templates are **SELECT-only**, bind parameters only, and may only reference
allowlisted business tables. Tools connect with `DATABASE_URL_READONLY`.

## RAG playbooks

Ingested from `data/playbooks/`:

- `revenue-drop-investigation.md`
- `stockout-escalation.md`
- `carrier-delay-response.md`
- `promo-postmortem.md`
- `returns-spike-triage.md`

Embeddings default to deterministic **local hashing** (384-d) so ingest works
without an LLM API key. Vectors live in `document_chunks.embedding` (pgvector).

## Persistence

Each successful tool call writes:

1. `investigations` (auto-created for standalone demos if id omitted)
2. `tool_invocations` (+ `source_id`)
3. `findings` (Evidence: claim, confidence, sources, assumptions, gaps)
4. `investigation_events` timeline row

`packages/opsmind/grounding` exposes an in-process `SourceIdRegistry` stub for
later citation verification (P4).
