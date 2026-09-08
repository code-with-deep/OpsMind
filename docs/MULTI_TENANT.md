# Multi-tenant — inventory, migration plan & status

**Branch:** `feature/multi-tenant`  
**Status:** MT0–MT6 complete (CSV + warehouse connector).  
**Related:** `AGENTS.md`, canvas `opsmind-multi-tenant-implementation-roadmap.canvas.tsx`

### Phase status (summary)

| Phase | Status |
|-------|--------|
| MT0 Prep | done |
| MT1 Tenancy core | done |
| MT2 Signup & invites | done |
| MT3 Playbooks & RAG | done |
| MT4 CSV data plane | done |
| MT5 Product harden | done |
| MT6 Warehouse connector | done |

### Operator path (MT5/MT6 exit)

1. Signup → Admin + tenant  
2. Invite → Investigator joins same tenant  
3. Upload CSV ZIP **or** connect verified warehouse → ready  
4. Upload playbook  
5. Investigate → approve → case memory  

---

## 1. Goals (locked)

- Shared Postgres + `tenant_id` + RLS  
- Self-serve signup (Admin) + invite codes (Investigator)  
- CSV data in MVP; warehouse = MT6  
- Same ecommerce/warehouse schema for all early tenants  
- OpenAI `text-embedding-3-small` for playbooks (MT3)

---

## 2. Table inventory — needs `tenant_id`

### 2.1 New control-plane tables (create in MT1)

| Table | Purpose |
|-------|---------|
| `tenants` | id (UUID), name, slug (unique), status, domain_profile, created_at |
| `users` | id, tenant_id FK, email (unique globally in MVP), password_hash, role (`admin` \| `investigator`), created_at |
| `api_keys` | id, tenant_id FK, name, key_hash, prefix (display), scopes JSONB, created_by, created_at, revoked_at |
| `tenant_settings` | tenant_id PK/FK, supported_domains JSONB, enabled_sql_templates JSONB, timezone, max_tool_calls, soft limits JSONB |
| `invite_codes` | id, tenant_id, code_hash, code_prefix, expires_at, max_uses, use_count, created_by, revoked_at *(can land in MT2 if MT1 stays schema-minimal)* |
| `ingest_jobs` | id, tenant_id, kind (`csv` \| `playbook`), status, error JSONB, created_at *(MT3/MT4)* |

### 2.2 Memory / investigation plane (add `tenant_id` NOT NULL after backfill)

| Table | Notes |
|-------|--------|
| `investigations` | Index `(tenant_id, created_at)` |
| `investigation_events` | Prefer tenant_id denormalized for RLS simplicity **or** join via investigation_id + policy |
| `tool_invocations` | Same |
| `findings` | Same |
| `reviews` | Same |
| `case_summaries` | Same + embedding stays |
| `documents` | Drop global unique on `doc_key` alone → unique `(tenant_id, doc_key)` |
| `document_chunks` | tenant_id (denormalized) for RAG filter performance |

**Recommendation:** Add `tenant_id` to child tables (`investigation_events`, `findings`, `tool_invocations`, `reviews`, `document_chunks`) as denormalized NOT NULL for simpler RLS and RAG SQL. Backfill from parent in migration.

### 2.3 Business plane (add `tenant_id` for CSV MVP)

| Table | Notes |
|-------|--------|
| `products` | Today `sku` globally unique → change to unique `(tenant_id, sku)` |
| `carriers` | unique `(tenant_id, name)` |
| `campaigns` | + tenant_id |
| `orders` | + tenant_id; keep internal ids |
| `order_items` | + tenant_id (denormalized) |
| `inventory_snapshots` | + tenant_id |
| `shipments` | + tenant_id |
| `returns` | + tenant_id |
| `daily_metrics` | unique `(tenant_id, metric_date)` instead of date alone if currently unique on date |

### 2.4 Out of DB / no tenant column

| Asset | Approach |
|-------|----------|
| LangGraph checkpoints | Namespace / thread id includes `tenant_id` when wiring MT1 runner |
| Object storage uploads | Path prefix `uploads/{tenant_id}/...` (MT3/MT4) |
| Env `OPSMIND_API_KEY` | Legacy bootstrapping → seed hashed key on **demo** tenant; prefer DB keys |

---

## 3. Default / demo tenant backfill plan (MT1 Alembic)

1. Create control-plane tables.  
2. Insert tenant:
   - `slug = 'demo'`
   - `name = 'OpsMind Demo'`
   - `domain_profile = 'ecommerce'`
3. Optional bootstrap admin user (disabled password until MT2) **or** only API key for demo.  
4. Insert hashed API key matching current `.env` `OPSMIND_API_KEY` value (or a dedicated `DEMO_API_KEY`) so existing curl/UI keep working.  
5. Add nullable `tenant_id` columns to all inventoried tables.  
6. `UPDATE … SET tenant_id = '<demo-uuid>' WHERE tenant_id IS NULL`.  
7. Alter `tenant_id` to `NOT NULL` + FK → `tenants.id`.  
8. Fix unique constraints (`sku`, `doc_key`, `daily_metrics` date, carrier name).  
9. Enable RLS + policies using `current_setting('app.tenant_id', true)::uuid`.  
10. App middleware: `SET LOCAL app.tenant_id = …` on each request/session used for tenant queries.

### Seed / playbooks after MT1

- `seed.py`: all inserts set `tenant_id=demo` (or accept tenant arg).  
- `ingest_playbooks.py`: attach chunks/docs to demo tenant until MT3 upload exists.

---

## 4. Env vars to introduce (document in `.env.example` during MT1/MT2)

| Variable | Phase | Purpose |
|----------|-------|---------|
| `JWT_SECRET` / `AUTH_SECRET` | MT2 | Web session/JWT signing |
| `OPENAI_API_KEY` or reuse embedding key | MT3 | `text-embedding-3-small` |
| `OPSMIND_EMBEDDING_PROVIDER=openai` | MT3 | Switch off local hashing in prod |
| `OPSMIND_API_KEY` | MT1 | Bootstrap hash into demo `api_keys` only |
| Soft limit defaults | MT1 settings | max upload MB, max investigations/day |

---

## 5. Suggested MT1 Alembic revision id

`0007_multi_tenant_core.py`

Keep one revision for control plane + tenant_id backfill if possible; split only if migration becomes too large.

---

## 6. Branch note (important)

As of MT0, `feature/multi-tenant` tip was at the pre-UI seed fix commit if branched from older `dev`.  
**Before heavy MT1 UI work**, merge or rebase onto the branch that contains the polished web console (`feature/ui` / updated `dev`) so login/settings screens match the current design system in `AGENTS.md` §6.

---

## 7. Exit criteria

| Phase | Exit |
|-------|------|
| **MT0** | This doc + AGENTS.md Next=`MT1` |
| **MT1** | Two tenants, two keys, zero cross-read in tests |
| **MT2–MT5** | See implementation roadmap canvas / `AGENTS.md` |
