# AGENTS.md — OpsMind Agent Working Guide

This file is the **source of truth for AI agents** implementing OpsMind.
Read it at the start of every session. Update the **Implementation Progress**
section when a phase finishes so the next agent can resume correctly.

Companion plans (open in Cursor canvases):

- **Implementation roadmap (execute this):** `opsmind-multi-tenant-implementation-roadmap.canvas.tsx`
- Multi-tenant architecture brief: `opsmind-multi-tenant.canvas.tsx`
- **Final multi-tenant plan:** `opsmind-multi-tenant-final-plan.canvas.tsx`
- Existing product architecture: `opsmind-final-architecture.canvas.tsx`

Repo docs: `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/SELF_CORRECTION.md`, `docs/TOOLS.md`, `docs/INVESTIGATIONS.md`, **`docs/MULTI_TENANT.md`** (MT0 inventory + MT1 migration plan).

---

## 1. What OpsMind is

Self-correcting **multi-agent operations intelligence** for ecommerce / warehouse ops.

- Operator asks a question → 6 LangGraph agents investigate → Critic may retry (max 2) → grounded recommendation → human approve/reject → case memory.
- **Cite-or-abstain**: every claim cites `sql_*` or `rag_*` evidence; otherwise abstain.
- **Not a chatbot.** Do not add free-form “answer without tools” paths.

### Current product status (single-tenant complete)

| Phase | Status |
|-------|--------|
| P0–P8 (foundation → demo) | **Done** |
| Operator UI polish / routing / responsive | Done (on branch; use dev compose for hot reload) |
| Multi-tenant | **MT0–MT6 complete (MVP + warehouse connector)** |

### Active git convention

- Multi-tenant work: branch **`feature/multi-tenant`** from latest **`dev`**.
- Do not mix unrelated UI polish into multi-tenant PRs.
- Never commit `.env` or real API keys.

---

## 2. Implementation Progress (UPDATE THIS)

Agents: when you complete a phase, set its status to `done`, fill **Completed**, and set **Next** to the following phase. If stopped mid-phase, note the exact files and remaining tasks under **Stopped mid-phase**.

| Phase | Status | Notes |
|-------|--------|-------|
| MT0 — Prep | `done` | Branch confirmed; `docs/MULTI_TENANT.md` inventory + default-tenant backfill plan; roadmap canvas |
| MT1 — Tenancy core | `done` | tenant/user/api_keys/tenant_settings tables; tenant_id on all tables; RLS; TenantContext auth; scoped queries in all agents/tools/routes; demo tenant backfill; two-tenant isolation test |
| MT2 — Signup & invites | `done` | Signup/login JWT; invite create/list/revoke/redeem; Admin vs Investigator; web login/signup/join/settings UI; api.ts prefers JWT over demo API key |
| MT3 — Playbooks & RAG | `done` | Per-tenant SOP upload (`/playbooks`); heading-aware 512–768 token chunks + overlap; OpenAI embeddings path (`dimensions=384`) + local for tests; RAG + list always tenant-scoped; Settings upload UI; Acme/Beta isolation test |
| MT4 — CSV data plane | `done` | ZIP CSV ingest (`/data/csv`); `ingest_jobs`; derive `daily_metrics`; ready-gate `409` on investigate; Settings Business data UI; soft row/size limits; Acme/Beta metrics isolation test |
| MT5 — Product harden | `done` | Company rename; API keys create/list/revoke; audit `tenant_id`+`user_id`; Settings keys UI; docs runbook; end-to-end two-tenant smoke |
| MT6 — Warehouse connector | `removed` | Feature fully removed (2026-09-08): routes, DB model, auth/secrets, test, nginx rule, frontend UI/state/types, API client methods, pyproject `cryptography` dep, `OPSMIND_SECRETS_KEY` env; migration 0011 drops the table. |
| — | — | Multi-tenant roadmap complete through MT5 (MT6 removed) |
| Invitation Access Request System + Notification Bells | `done` | Full invite-based access request workflow + in-app notifications (2026-09-08) |

**Last updated:** 2026-09-08 
**Next phase to implement:** _(none — MT0–MT5 complete + access request system + case memory wired)_ 
**Stopped mid-phase:** _(none)_ 
**Completed summary (Invitation Access Request System, 2026-09-08):** Added `access_requests` and `notifications` tables (migration `0012`); extended `users` with `status/revoked_at/revoked_by`; updated ORM models; changed `/auth/join` to create `AccessRequest` (pending) instead of User immediately; added `GET /auth/request-status` poll endpoint; new `/access/*` routes for admin approve/reject/list/revoke; new `/notifications/*` routes for bell count + list + mark-read; `NotificationBell.tsx` with polling, dropdown, mark-all-read; `Header.tsx` — bell added, API Key button removed; `SettingsPage.tsx` — Access Management section with Pending/Active/Revoked tabs; `JoinPage.tsx` — pending state + 10s polling; `RequireAuth.tsx` — 403 revoked screen; TypeScript build clean; Docker rebuilt.

**Completed summary (Case Memory wired into pipeline, 2026-09-08):** Added `packages/opsmind/agents/case_memory_agent.py` — new `case_memory_node` that queries pgvector for top-3 similar approved cases (cosine similarity ≥ 0.15), formats them as `kind="case_memory"` findings with proper `source_id` for citation verifier, skips on retries (retry_count > 0). Updated `builder.py` — inserted `case_memory` node between planner and data_investigator; `_route_after_planner` now routes to `case_memory` (not directly to `data_investigator`). Updated `synthesizer.py` — heuristic and LLM paths both handle `case_memory` findings (historical context, not current-period numbers). Updated `recommender.py` LLM prompt to treat case memory as context only. Added `reset_graph_cache()` call on module reload in `runner.py`. Circular import resolved via deferred in-function import of `query_similar_cases`.

**Completed summary:** MT0 — table inventory (business + memory + RAG), control-plane table list, demo-tenant backfill steps for Alembic `0007`, env foreshadow, branch note to merge UI before MT2 screens. MT1 — Alembic `0007_multi_tenant_core` creates tenants/users/api_keys/tenant_settings, adds `tenant_id` NOT NULL to all 17 business+memory+RAG tables, backfills demo tenant, enables RLS policies. `TenantContext` replaces global API key auth. Agents/tools/routes enforce `tenant_id`. Two-tenant isolation test. MT2 — Alembic `0008_invite_codes`; signup creates tenant+Admin; invite redeem → Investigator; JWT web sessions (`JWT_SECRET`); `/auth/*` routes; login/signup/join/settings UI; `api.ts` sends Bearer JWT preferentially; invite admin UI with soft limits. MT3 — `POST/GET/DELETE /playbooks`; files under `data/uploads/{tenant_id}/playbooks/`; `chunk_markdown` token-band + overlap; `embed_texts` dispatches local|openai (`text-embedding-3-small` with `dimensions=384`); `retrieve_playbooks` uses provider-aware query embed + `WHERE tenant_id`; Settings Playbooks section; soft limits `max_playbooks` / `max_playbook_upload_bytes`; `test_mt3_playbooks_rag.py` proves Acme never retrieves Beta chunks. MT4 — Alembic `0009_ingest_jobs`; `POST /data/csv` ZIP (products/orders/order_items + optional); tenant-scoped replace + derived `daily_metrics`; `GET /data/ready` + investigate ready-gate; Settings Business data + ingest job list; `test_mt4_csv_data_plane.py`; sample templates in `data/csv_templates/`. MT5 — `PATCH /auth/tenant`; `/auth/api-keys` CRUD + soft limit; audit payload `tenant_id`/`user_id`; Settings company edit + API keys; SECURITY/DEMO/MULTI_TENANT/README updates; `test_mt5_product_harden.py` full path smoke. API keys management (removed 2026-09-08) — create/list/revoke UI+endpoints removed; underlying auth lookup (`ApiKey` model/table, `hash_api_key`, `resolve_tenant_from_api_key`, env-var demo bootstrap) kept intact; removed `CreateApiKeyBody`, `POST/GET /auth/api-keys`, `POST /auth/api-keys/{id}/revoke`; removed `generate_api_key`+`key_prefix` from `auth/api_keys.py` + `auth/__init__.py`; removed `auth_max_api_keys` config + `max_api_keys` soft limit from signup; removed Settings UI section + `ApiKeyItem` type + api.ts methods; updated test_mt5. MT6 (removed 2026-09-08) — warehouse connector feature fully removed end-to-end: deleted `routes/warehouse.py`, `db/warehouse.py`, `auth/secrets.py`, `test_mt6_warehouse_connector.py`; stripped `WarehouseConnection` model + `Tenant.warehouse_connection` relationship; simplified `sql_tool._resolve_factory` to shared-engine only; removed `warehouse_ready` from `tenant_data_ready`; removed warehouse router from `main.py` + nginx rule; removed `opsmind_secrets_key` config + `OPSMIND_SECRETS_KEY` env var + `cryptography` pip dep; removed all warehouse UI/state/types from `SettingsPage.tsx` and `api.ts`; created migration `0011_remove_warehouse_connections` to drop the DB table. **Post-MT6 pipeline grounding (2026-09-07):** planner parses explicit compare windows from the question (no demo Aug defaults when dates present); strips pre-tool money claims; tenant-agnostic SQL plan + `inventory_low_stock`; synthesizer/recommender copy numbers from findings only; critic retries on `numeric_mismatch_with_sql_evidence`; SQL findings keep up to 50 rows.
### Resume checklist for every new agent session

1. Read this file (especially §2 Progress + §4 Locked decisions + §2b Post-implementation).
2. `git branch --show-current` — expect `feature/multi-tenant` once created.
3. `git status` / skim recent commits on the branch.
4. Implement **only the Next phase** unless the user explicitly expands scope.
5. After finishing: follow **§2b mandatory close-out** (update this file + rebuild Docker). Do not leave those steps for the user.

### 2b. Mandatory close-out after code / phase work (AGENT DOES THIS)

**Do not ask the user to update docs or rebuild Docker from the terminal.** After any meaningful implementation (a finished phase, or a stop mid-phase with working changes), the agent **must** run this close-out itself:

1. **Update this file (`AGENTS.md`)**
   - Set the finished phase status to `done` (or leave current as `in_progress` / note under **Stopped mid-phase**).
   - Set **Next phase to implement** to the following phase.
   - Refresh **Last updated** (ISO date).
   - Append a short **Completed summary** line (what shipped).
   - If blocked mid-phase: list exact remaining tasks and files under **Stopped mid-phase**.
2. **Verify the build** when web or API code changed
   - Web: `cd apps/web; npm run build` (fix TypeScript errors before Docker).
   - Tests when relevant: `pytest packages/opsmind/tests apps/api/tests -q`.
3. **Rebuild and restart Docker** so the running app picks up changes
   - Prefer **dev hot-reload stack** for local work:
     ```powershell
     docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
     ```
   - If the user is on **production-style** compose (no dev overlay), use:
     ```powershell
     docker compose up --build -d
     ```
   - If only API Python packages changed and containers are already on the dev overlay with bind mounts + reload, still **`--build`** when `Dockerfile`, dependencies, or env templates changed.
4. **Confirm stack health** (agent runs these, not the user)
   ```powershell
   docker compose ps
   ```
   - Smoke: API `http://localhost:8000/health` (or `/ready`) and web `http://localhost:3000` when those ports are in use.
5. **Tell the user** briefly: what was implemented, that `AGENTS.md` was updated, and that Docker was rebuilt — with any URL/port notes.

**Skip Docker rebuild only if** the change was docs-only (e.g. only `AGENTS.md` / canvas text) with no runtime code. Still update §2 if progress changed.

**Never** leave the user with “please run docker compose yourself” after an implementation session unless Docker is unavailable in the environment — then state that explicitly and give the exact command as a fallback.

---

## 3. Locked multi-tenant decisions (do not reopen without user OK)

| Topic | Decision |
|-------|----------|
| Goal | Self-serve SaaS MVP (phased) |
| DB | Shared Postgres + `tenant_id` + RLS |
| Auth | Email/password + per-tenant API keys (hashed) |
| Roles | **Admin** (signup user) + **Investigator** (invite code) |
| Membership | One user ↔ one company |
| Invites | Admin generates invite code; employee joins that tenant |
| Domain | Same ecommerce/warehouse schema for all early tenants |
| Data MVP | **CSV upload first** |
| Data later | Warehouse/Postgres connector = **MT6 only** |
| Demo data | Not for real production tenants |
| Playbooks | Each company uploads own SOPs |
| Embeddings | OpenAI `text-embedding-3-small` (local hashing = tests/CI only) |
| Chunking | Heading-aware, **512–768 tokens**, ~10–15% overlap |
| Billing | Out of scope; **soft usage caps required** |
| Host | Docker Compose |
| Branch | `feature/multi-tenant` |

### Invite / role rules

- Signup → create `tenant` + user as **Admin**.
- Invite code → bound to one tenant; redeem → **Investigator** only.
- Reject join if user already belongs to another tenant.
- Admin can rotate/revoke codes; support expiry.

### Security non-negotiables

- Derive `tenant_id` from auth only — **never** trust client-sent tenant id.
- Fail closed if TenantContext missing.
- Every tenant-owned query filtered by `tenant_id` **and** prefer Postgres RLS.
- Allowlisted SQL only — no customer-authored SQL.
- Soft limits: upload size, investigations/day, playbooks, API keys, invite uses.

---

## 4. Repository structure

```text
OpsMind/
├── apps/
│   ├── api/                 # FastAPI app (package name: api)
│   │   └── app/
│   │       ├── main.py
│   │       ├── auth.py      # Today: global OPSMIND_API_KEY — replace in MT1/MT2
│   │       ├── config.py
│   │       └── routes/      # health, investigations, tools
│   └── web/                 # React 19 + Vite + Tailwind operator console
│       └── src/
│           ├── pages/       # Route pages
│           ├── layouts/     # AppShell
│           ├── components/  # UI by domain (landing, investigation, …)
│           ├── lib/         # api.ts, routes.ts, utils.ts
│           └── types/
├── packages/opsmind/        # Shared domain library (import: opsmind.*)
│   ├── agents/              # planner, data_investigator, knowledge, …
│   ├── graph/               # LangGraph builder, runner, state
│   ├── tools/               # sql_tool, rag_tool, sql_templates, embeddings
│   ├── guardrails/
│   ├── grounding/
│   ├── memory/
│   ├── domain/
│   └── db/                  # models, memory_models, alembic, seed, ingest_playbooks
├── data/playbooks/          # Demo SOPs (global today → per-tenant in MT3)
├── docs/
├── evals/
├── docker-compose.yml
├── docker-compose.dev.yml
└── pyproject.toml
```

### Import / package layout

- Python: `api.*` maps to `apps/api`; `opsmind.*` maps to `packages/opsmind`.
- Web: path aliases as in existing Vite/TS config; prefer `@/` only if already configured — otherwise relative imports matching neighbors.
- Alembic lives under `packages/opsmind/db/alembic/` — new schema changes = new revision, never edit old migrations casually.

---

## 5. Coding rules

### General

- **Small, focused diffs.** No drive-by refactors unrelated to the current phase.
- Match existing naming, file layout, and patterns before inventing new ones.
- Do not add markdown docs the user did not ask for (except updating this `AGENTS.md` progress section).
- No secrets in git. Use `.env.example` for new env vars with placeholders.
- Prefer extending existing modules (`auth.py`, `AppUI.tsx`, `sql_templates.py`) over parallel duplicate systems.

### Backend (Python / FastAPI)

- Python **3.11+**, FastAPI, SQLAlchemy 2.x style (`Mapped`, `mapped_column`).
- Settings via `pydantic-settings` in `api.app.config`.
- Protected routes today use `Depends(require_api_key)` — evolve to TenantContext without breaking health/ready/docs public access.
- SQL tools: parameterized templates only; `FORBIDDEN_SQL_RE` + allowlisted tables must remain.
- Graph: keep Critic loop (`pass` / `retry` / `fail_soft`); max retries from settings.
- Persist evidence via existing memory helpers; do not bypass `tool_invocations` / `findings`.
- Tests: `pytest` under `packages/opsmind/tests` and `apps/api/tests`. Add isolation tests for two tenants as soon as MT1 exists.
- Use type hints; avoid bare `except:`.

### Frontend (React / TypeScript)

- React 19 + TypeScript + Tailwind. Functional components only.
- Routing: React Router — add routes in `App.tsx` / `lib/routes.ts` consistently.
- Shared chrome: `layouts/AppShell.tsx` + `components/layout/Header.tsx`.
- Reuse `components/common/*` (`Button`, `Modal`, `Badge`, `PageHeader`, `AppUI`, `OpsMindLogo`) before new primitives.
- API calls go through `lib/api.ts` — do not scatter raw `fetch` with ad-hoc auth headers.
- Prefer existing patterns (`SectionCard`, `SearchBar`, `FilterPills`, `ListCard`, `EmptyState`, `SubViewTabs`).
- Do not add `useMemo` / `useCallback` by default unless the codebase pattern needs it.
- Keep pages thin: data/orchestration in shell or hooks; presentation in components.

### Agents / tools (multi-tenant)

- Inject **TenantContext** into graph `runtime` (alongside `database_url_sync`, budgets, etc.).
- Planner domains / enabled SQL templates come from **tenant_settings**, not hardcoded globals (migrate gradually from `triage.py` defaults).
- RAG queries **must** filter `tenant_id`.
- SQL against internal tables **must** include tenant scope (session GUC + RLS and/or explicit predicate).
- Tabular business data is **not** embedded — SQL only. Embeddings are for playbooks + case summaries.

---

## 6. Frontend design system (keep one theme)

The app already has a dark green OpsMind theme. **New screens must match it** — do not introduce a second visual language (no purple SaaS defaults, no cream/serif marketing mashup on app routes).

### Brand & color

| Token / usage | Value / rule |
|---------------|--------------|
| App background | `#030712` / `surface-950` (`app-shell`) |
| Panels | `.app-panel`, `.app-section`, `.app-card` glass dark surfaces |
| Accent | Green `accent-400`–`accent-600` (CTAs, active nav, focus) |
| Text | `surface-100` primary, `surface-400` secondary |
| Danger / success | rose / emerald sparingly for status only |

- Prefer **`variant="accent"`** buttons in the app shell; avoid purple `brand` gradients on new app pages (landing may retain some legacy brand tokens until unified).
- Focus rings: accent, not indigo/purple.

### Typography

| Surface | Font | Tailwind / class |
|---------|------|------------------|
| Landing hero | Fraunces | `font-display` |
| Landing section titles | DM Serif Display | `font-heading` |
| Landing subheads | Merienda | `font-subheading` |
| **App routes** (console, history, …) | Vollkorn for headings | `font-app-heading` / `.app-shell h1,h2,h3` |
| Body / UI | Inter | `font-sans` |
| Code / IDs | JetBrains Mono | `font-mono` |

### Layout & components

- Use `.app-section`, `.app-section-header`, `.app-section-body`, `.app-prose`, `.app-search-*`, `.app-filter-*`, `.app-tab-*`, `.app-list-card`, `.app-stat-chip`, `.app-empty`.
- Page titles via `PageHeader`.
- Modals: bottom-sheet on mobile (`Modal.tsx` pattern), safe-area padding.
- Touch targets ≥ ~44px; search inputs ≥ 16px font on mobile (avoid iOS zoom).
- Responsive: stack on small screens; avoid fixed `max-h` scroll traps — use `.app-scroll-panel` / `min(60vh, …)`.

### Landing vs app

- Landing (`/`) is marketing: brand-first hero, landing fonts, no app chrome.
- App routes use `AppShell` + Vollkorn headings + green accent chrome.
- New multi-tenant pages (login, signup, settings, invite, upload) are **app-theme**, not a new landing style.

### Motion & polish

- Prefer existing `animate-fadeIn` / `animate-slide-up`.
- No emoji as UI icons — use `lucide-react`.
- No gratuitous glow stacks or rainbow pills.

---

## 7. Phase playbooks (implement in order)

### MT0 — Prep

- [x] Create / confirm `feature/multi-tenant`.
- [x] Inventory tables needing `tenant_id` (business + memory + documents).
- [x] Plan migration: assign existing rows to a `demo` tenant (`docs/MULTI_TENANT.md`).
- [x] Implementation roadmap canvas.
- **Exit:** plan written; Next = MT1. **Done 2026-09-03.**

### MT1 — Tenancy core

- [x] Tables: `tenants`, `users`, `api_keys`, `tenant_settings`.
- [x] Add `tenant_id` to investigations, events, findings, tool_invocations, reviews, case_summaries, documents/chunks, business tables.
- [x] `TenantContext` dependency; replace single global key lookup with hashed per-tenant keys (keep a bootstrapping story for demo tenant).
- [x] Enable RLS where practical.
- [x] Soft limit fields on settings.
- **Exit:** two tenants / two keys — zero cross-visibility in list/get/run tests.

### MT2 — Signup & invites

- [x] Signup API + UI (password hashed; email verify deferred).
- [x] Signup user = Admin; creates tenant.
- [x] Invite codes: create / list / revoke / redeem → Investigator.
- [x] Login UI; JWT for web; wire `api.ts` to prefer JWT over shared localStorage default key.
- **Exit:** invite join lands user in correct tenant only.

### MT3 — Playbooks & RAG

- Upload SOP → store under tenant → chunk (512–768 tokens, heading-aware) → OpenAI embeddings.
- `OPSMIND_EMBEDDING_PROVIDER=openai` path production-ready; local for tests.
- RAG `WHERE tenant_id = :id`.
- **Exit:** Acme retrieval never returns Beta chunks.

### MT4 — CSV data plane

- [x] Upload CSV → validate → map to ecommerce schema → insert with `tenant_id`.
- [x] `ingest_jobs` status UI; ready-gate before investigate.
- [x] Soft file/row limits.
- **Exit:** investigation metrics match that tenant’s file. **Done 2026-09-04.**

### MT5 — Product harden

- [x] Settings: company profile, invites, API keys, upload status.
- [x] Audit payloads include `tenant_id` + `user_id`.
- [x] Docs/runbook update; two-tenant smoke / eval.
- **Exit:** full path signup → invite → CSV → playbook → investigate → approve. **Done 2026-09-04.**

### MT6 — Warehouse (post-MVP)

- [x] Read-only connector + secrets; allowlisted SQL on tenant engine.
- **Exit:** verified warehouse satisfies ready-gate; unverified fails closed; secrets never returned. **Done 2026-09-04.**

---

## 8. Runtime & verification commands

Agents run these as part of **§2b close-out** after implementation. Default local URLs: web `http://localhost:3000`, API `http://localhost:8000`, docs `/docs`.

```powershell
# 1) Web typecheck / production build (when frontend changed)
cd apps/web; npm run build

# 2) Python tests (when backend / agents / db changed)
pytest packages/opsmind/tests apps/api/tests -q

# 3) Rebuild + restart — DEV (preferred for day-to-day)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

# 3b) Rebuild + restart — production-style static web image
docker compose up --build -d

# 4) Confirm containers
docker compose ps
```

If compose project is already running, `up --build -d` is enough (no need for `down` unless volumes/migrations require a clean reset — avoid destructive volume wipes unless the user asks).

---

## 9. Out of scope (reject unless user explicitly expands)

- Billing / Stripe  
- SSO / OAuth  
- Viewer role, multi-company users  
- Custom per-tenant DB schemas  
- Customer-authored SQL  
- Fine-tuned models per tenant  
- DB-per-tenant  
- Write-back side effects to customer systems  
- Replacing cite-or-abstain or removing Critic self-correction  

---

## 10. Definition of done (per phase)

- Code matches this guide’s theme and structure rules.
- Tenant isolation not weakened.
- Tests or manual smoke for the phase exit criteria.
- **§2 Progress updated by the agent.**
- **Docker rebuilt/restarted by the agent** (§2b) when runtime code changed.
- No unrelated refactors; no committed secrets.
- User is informed that progress file + Docker were handled — they should not need to run terminal rebuild steps.

---

## 11. Quick file map for common tasks

| Task | Start here |
|------|------------|
| Auth / API key | `apps/api/app/auth.py`, `apps/api/app/routes/*` |
| Investigation run | `packages/opsmind/graph/runner.py`, `builder.py` |
| SQL templates | `packages/opsmind/tools/sql_templates.py`, `sql_tool.py` |
| RAG / embeddings | `packages/opsmind/tools/rag_tool.py`, `embeddings.py`, `db/ingest_playbooks.py` |
| Critic / retry | `packages/opsmind/agents/critic.py`, `planner.py` |
| DB models | `packages/opsmind/db/models.py`, `memory_models.py` |
| Web API client | `apps/web/src/lib/api.ts` |
| Routes | `apps/web/src/lib/routes.ts`, `App.tsx` |
| Design tokens / app CSS | `apps/web/src/index.css`, `tailwind.config.js` |
| Shared UI | `apps/web/src/components/common/AppUI.tsx` |

---

_End of AGENTS.md. Keep progress (§2) honest — that is how handoffs work._
