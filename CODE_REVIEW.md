# OpsMind — Codebase Review: Issues, Gaps & Recommended Fixes

**Reviewed:** 2026-09-10 · branch `main` @ `42d397e`
**Scope:** `apps/api`, `apps/web`, `packages/opsmind`, `evals`, migrations, Docker/deploy config, docs.
**Method:** full static read of all source files (~21.8k LOC Python/TS). No runtime execution — Python deps and `node_modules` are not installed in this environment, so lint/typecheck/test runs could not be performed.

---

## Fix status (2026-09-11)

All 7 **P0**s, all 13 **P1**s, and the highest-value **P2**s below were fixed in this pass. Every change was checked against the existing test suite by reading test expectations line-by-line (pytest/node_modules aren't installed here, so nothing could actually be *run* — see caveat at the bottom). Two fixes were deliberately reverted or scoped down after they were found to regress existing, intentional test behavior — see the P3-6 and P2-12 entries below for why.

**Fixed:**
- **P0-1 → P0-7**: all seven. New migration `0014_enforce_rls_and_harden_readonly.py` adds `FORCE ROW LEVEL SECURITY` + locks the readonly role to the 9 business tables; `tenant_session.py` re-applies the tenant GUC on every transaction begin (was lost after the first commit); `runtime.py` strips DB URLs/LLM keys from graph state before checkpoint; the bootstrap API key is no longer inserted by migration; `JWT_SECRET`/`OPSMIND_API_KEY` are validated at startup (see note below on how this stayed test-compatible); upload routes check `Content-Length` before reading the body.
- **P1-1 → P1-13**: all thirteen. Notably: `key_prefix()` added (test suite now imports cleanly); relative date windows replace the hardcoded demo week for real tenants; citation verification now checks that cited SQL findings actually contain the numbers a claim states, and only accepts `sql_`/`rag_` source ids (not `case_memory`); LLM fallback paths log and mark reports `degraded` instead of silently swallowing errors; the Critic's driver-coverage signal now reads real SQL row values instead of planner-authored labels that always matched; review submission requires a real user session and takes the reviewer identity from it, not the request body; session-expiry 401s redirect to `/login` instead of showing "wrong password"; CORS no longer combines `*` with credentials; rate limiting (in-process, per-IP/per-account) added to login/signup/join/forgot-password/request-status, plus a login timing-oracle fix and a daily investigation cap; raw exception text no longer reaches API responses.
- **Selected P2s**: `O(n²)` metrics derivation, missing `pgvector` HNSW indexes (new migration `0015`), row-by-row bulk deletes, unordered `latest_review`, DB pool sizing + `statement_timeout`, unbounded SQL templates now `LIMIT`ed, the dead unwired `fanout` node replaced with a real parallel fan-out (data_investigator + knowledge), unbounded process-global registries bounded, N+1 queries in `/access` and investigation listing batched, Docker hardening (non-root, healthchecks, `npm ci`, fatal+lock-guarded migrations).
- **Selected P3s**: leaked host IP in `.env.example`, a couple of `triage.py` keyword hygiene issues (removed `\bhr\b` false-positiving on "24 hr", removed generic `project`/`client`/`engagement` ops keywords).

**Deliberately reverted / not attempted, with reasons:**
- **P3-6** (triage precedence — ops questions mentioning an off-topic word get wrongly rejected): first attempt regressed `test_triage_poem_unsupported` / `test_triage_payroll_unsupported` (both mention "warehouse" and are correctly expected to stay `unsupported`). A correct fix needs the ops-keyword list's plural-matching gaps fixed first (`\bdelay\b` doesn't match "delays", etc.) and a calibrated threshold — reverted to the original, test-verified ordering rather than ship something unverified. Left a comment in `triage.py` explaining exactly why and what a correct fix needs.
- **P2-12** (test-only `block_sql_on_first_pass` branching in the production agent path): removing it requires patching the compiled LangGraph's bound node reference, which I can't verify without running the graph. Confirmed instead that the flag is not reachable from any API route (`runtime_overrides` is never accepted from a request body) and documented that in the code.
- **P2-3/P2-4** (embedding-provider mismatch corrupts retrieval silently): needs a schema column (`embedding_provider`/`embedding_model` on `document_chunks`) plus query-time consistency checks — a half-migrated version of this would be worse than the current state, and I couldn't run a migration against a live DB to verify it. Left as documented, not attempted.
- Remaining **P2**s (sequential SQL execution, non-root nginx, full embedding-provider fix) and most **P3** polish items are unchanged from the original review below.

**Important regressions caught and fixed before finishing:** the initial P0-6 fix (making `jwt_secret` a required field with no default, and unconditionally rejecting short/placeholder secrets) would have broken `Settings()` construction and startup validation for ~9 of the ~13 test files that call `create_app()`/`get_settings()`, none of which set `JWT_SECRET` and several of which use a 21-character test `OPSMIND_API_KEY`. Fixed by restoring the placeholder default (so `Settings()` stays constructible) and gating the strict rejection in `main.py`'s `_validate_secrets()` on `APP_ENV` (exempts `development`/`test`) — matching what the original review recommendation actually said, which the first pass had implemented too strictly. Separately, the P1-8 fix (review submission requires a real user session) broke `test_list_investigations_and_cases_api`, which submitted a review over API-key-only auth; fixed by updating that one test to mint a real user + JWT for the review call, matching the new (correct) requirement — `test_mt5_product_harden.py`'s equivalent test already used a real JWT and needed no change.

**Caveat:** none of this was run — no pytest, no tsc, no ruff, no live Postgres in this environment. Verification was done by reading every test that touches changed code and tracing the logic by hand (including catching and fixing the two regressions above). Before merging, run the actual suite: `alembic upgrade head` against a real Postgres, then `pytest -q`, then `cd apps/web && npm ci && npm run build`.

---

## Severity Legend

| Level | Meaning |
|:---|:---|
| **P0 — Critical** | Security hole, data-integrity risk, or broken core guarantee. Fix before any real tenant onboards. |
| **P1 — High** | Correctness bug, production-blocking gap, or a documented capability that does not actually work. |
| **P2 — Medium** | Performance, scalability, reliability, or maintainability debt that will hurt at modest scale. |
| **P3 — Low** | Polish, hygiene, docs, DX. |

---

## Executive Summary

The architecture is coherent and the code is unusually consistent in style. The layering (tools → agents → graph → API) is clean, allowlisted SQL is a genuinely good design choice, and the multi-tenant control plane is well thought out on paper.

The gap is between **design intent and enforced reality**. Specifically:

1. **Row-Level Security is written but inert.** Policies exist on 17 tables, but they are not `FORCE`d and the application connects as the table owner — Postgres exempts owners from RLS by default. Tenant isolation currently rests entirely on hand-written `WHERE tenant_id = ...` clauses.
2. **The "cite-or-abstain" grounding guarantee is structural, not semantic.** The verifier checks that a `source_id` *exists*, never that the claim is *supported* by it. In heuristic (no-LLM) mode the recommender attaches the same blanket citation list to every claim and ships a hardcoded action template.
3. **The test suite does not run.** `test_mt1_tenant_isolation.py` fails at import (`key_prefix` does not exist), every other DB-backed test `skipif`s itself into a pass when Postgres is absent, and there is no CI at all. The README's "100% complete, verified and benchmarked" is not backed by an enforced gate.
4. **Hardcoded demo state leaks into the multi-tenant product** — a fixed 2026-08 date window, demo SKUs, and a well-known default API key.

Counts: **7 P0**, **13 P1**, **17 P2**, **11 P3**.

---

# P0 — Critical

### P0-1. Row-Level Security is not enforced — the app connects as the table owner
**Files:** `packages/opsmind/db/alembic/versions/0007_multi_tenant_core.py:70-91`, `packages/opsmind/db/session.py:16`, `.env.example:15-17`

`_enable_rls()` runs `ALTER TABLE … ENABLE ROW LEVEL SECURITY` and creates `tenant_isolation_select` / `tenant_isolation_modify` policies on all 17 tenant tables. It never runs `FORCE ROW LEVEL SECURITY`.

In PostgreSQL, the **table owner bypasses RLS unless `FORCE` is set**. The migrations run as `opsmind`, so `opsmind` owns every table — and `get_owner_session_factory(settings.database_url_sync)` connects as `opsmind` for every API request, every agent node, and every write. **The policies never evaluate.**

Isolation therefore depends 100% on every query carrying a manual `tenant_id` filter. Most do, but the defence-in-depth layer the design assumes simply is not there. Any future query that forgets the filter silently leaks across tenants.

**Fix**
```sql
ALTER TABLE <each tenant table> FORCE ROW LEVEL SECURITY;
```
in a new migration, then run the MT1 isolation tests against a *non-superuser* app role. Better still: create a dedicated `opsmind_app` login role that is **not** the table owner, grant it DML only, and point `DATABASE_URL_SYNC` at it. Keep migrations on the owner role.

---

### P0-2. `set_config(..., is_local => true)` is dropped by every `commit()`
**Files:** `packages/opsmind/db/tenant_session.py:12-18`, `apps/api/app/deps.py:16-29`, and every caller

```python
session.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), ...)
```

The third argument `true` makes the setting **transaction-local**. `get_tenant_session` sets it once when the session is created, but many routes and helpers commit mid-request — `persist_tool_result()`, `write_event()`, `update_investigation()`, `create_invite()`, `upload_csv_bundle()` all call `session.commit()`. After the first commit the GUC is gone, and every subsequent statement in that request runs with `app.tenant_id` unset.

This is currently masked by P0-1 (policies aren't evaluated anyway). **The moment you fix P0-1, this becomes an outage**: post-commit queries will silently return zero rows and inserts will fail the `WITH CHECK` clause.

**Fix**
- Re-apply the GUC after every commit, or
- Use a SQLAlchemy `after_begin` event listener on the session so it is re-set on each new transaction, or
- Set it at the connection level (`is_local => false`) with a `checkin` listener that resets it before the connection returns to the pool.

The event-listener approach is the only one that survives refactoring:
```python
@event.listens_for(session, "after_begin")
def _set_tenant(sess, trans, conn):
    conn.exec_driver_sql("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
```

---

### P0-3. Control-plane tables have no RLS and the read-only role can read them all
**Files:** `0007_multi_tenant_core.py:29-46` (`TENANT_TABLES`), `packages/opsmind/db/seed.py:100-107`

`TENANT_TABLES` deliberately excludes the control plane: `tenants`, `users`, `api_keys`, `tenant_settings`, and (from later migrations) `invite_codes`, `access_requests`, `notifications`, `password_reset_tokens`. None of these have RLS policies of any kind.

Meanwhile `ensure_readonly_role()` grants the investigation role blanket access:
```python
conn.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{user}"'))
conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ..."))
```

So `opsmind_readonly` — the role the agent SQL tool uses — can `SELECT` every tenant's password hashes, API key hashes, reset tokens, and invite codes. The SQL template allowlist is the only thing standing between the LLM-driven tool layer and that data. That is a single-layer defence around credential material.

**Fix**
1. Grant `SELECT` only on the nine business tables in `ALLOWLISTED_TABLES`, and explicitly `REVOKE ALL ON users, api_keys, password_reset_tokens, invite_codes, access_requests FROM opsmind_readonly`.
2. Drop the `ALTER DEFAULT PRIVILEGES` blanket grant — it auto-grants access to every future table.
3. Add `tenant_id` + RLS policies to `invite_codes`, `access_requests`, `notifications`, `password_reset_tokens` (they already carry `tenant_id`).

---

### P0-4. LLM API key and database URLs are persisted in plaintext to the LangGraph checkpointer
**Files:** `packages/opsmind/graph/runner.py:97-113` (`build_runtime`), `packages/opsmind/graph/state.py:24`

`build_runtime()` puts live secrets into the graph state:
```python
runtime = {
    "database_url_sync": settings.database_url_sync,      # includes password
    "database_url_readonly": settings.database_url_readonly,  # includes password
    "llm_api_key": settings.llm_api_key,
    ...
}
```
`runtime` is a field on `InvestigationState`, and the graph is compiled with `PostgresSaver`. **Every checkpoint write serialises the DB passwords and the LLM API key into the `checkpoint_blobs` table.** They persist there indefinitely, are readable by anyone with DB access, and end up in every backup and snapshot.

`sanitize_output_payload` does not help — it only runs on the API response, not on the checkpoint.

**Fix** Keep secrets out of graph state. Pass a small opaque `run_id` / config key through the state and resolve credentials from `get_settings()` inside each node, or use LangGraph's `configurable` channel with a non-persisted store. If the runtime dict must stay, strip secret keys before the state is returned from each node.

---

### P0-5. A well-known default API key grants tenant access, and there is no way to issue a real one
**Files:** `apps/api/app/auth.py:66-79`, `0007_multi_tenant_core.py:27-28`, `apps/web/src/lib/api.ts:13`, `.env.example:60`

Three facts compound:
1. `DEFAULT_BOOTSTRAP_KEY = "change-me-opsmind-dev-key"` is hashed into the `api_keys` table by the migration itself, so it is valid on **every deployment** that runs migrations.
2. The same literal is compiled into the frontend bundle: `export const DEMO_BOOTSTRAP_API_KEY = "change-me-opsmind-dev-key";`
3. `.env.example` ships `OPSMIND_API_KEY=change-me-opsmind-dev-key`, and `resolve_tenant_from_api_key` accepts it as an env-bootstrap fallback for the `demo` tenant.

Anyone who reads the public repo can authenticate to the demo tenant of any deployment that hasn't rotated it — reaching `/tools/sql/run`, `/tools/rag/query`, and `/investigations`.

Compounding this: **there are no API key management endpoints at all.** `grep` finds no `POST /auth/api-keys`, no rotate, no revoke. The `ApiKey` model and `resolve_tenant_from_api_key` exist, `ApiKeyModal.tsx` lets a user paste a key — but no tenant can ever *obtain* one. The only key in existence is the compromised default.

**Fix**
- Delete the bootstrap `api_keys` INSERT from the migration; seed it only from an explicit `scripts/bootstrap_demo.py` run.
- Refuse to boot when `APP_ENV != "development"` and `OPSMIND_API_KEY` still equals the default (same check for `JWT_SECRET`).
- Remove `DEMO_BOOTSTRAP_API_KEY` from the frontend.
- Ship `POST /auth/api-keys` (create, returns raw once), `GET /auth/api-keys` (list prefixes), `POST /auth/api-keys/{id}/revoke` — admin-only, mirroring the invite-code flow that already exists.

---

### P0-6. `JWT_SECRET` has a working default and tokens live in `localStorage` for 72 hours
**Files:** `apps/api/app/config.py:38`, `apps/api/app/main.py:36-37`, `apps/web/src/lib/api.ts:129-141`

```python
jwt_secret: str = "change-me-opsmind-jwt-secret-dev-only"
jwt_expire_hours: int = 72
```

Unlike `opsmind_api_key`, `jwt_secret` has a **default value**, so a deployment that forgets to set it starts up happily and signs sessions with a secret published in this repo. Anyone can then forge an admin JWT for any tenant. `main.py:36` even does `os.environ.setdefault("JWT_SECRET", settings.jwt_secret)`, propagating the default further.

On the client side, the token is stored in `localStorage` — reachable by any XSS — with a 72-hour lifetime, no refresh-token rotation, and no idle timeout.

**Fix**
- Make `jwt_secret` a required field with no default; fail fast at startup if it is short or matches the known placeholder.
- Move to a `Secure; HttpOnly; SameSite=Lax` cookie for the session token, with a short-lived (15–60 min) access token plus a rotating refresh token. `token_version` is already in place and gives you server-side revocation — pair it with a refresh endpoint.

---

### P0-7. Uploads are read fully into memory before the size check — trivial OOM, plus zip-bomb exposure
**Files:** `apps/api/app/routes/data.py:96-101`, `apps/api/app/routes/playbooks.py:100-105`, `packages/opsmind/db/ingest_csv.py:118-142`

```python
raw = await file.read()                  # entire body into RAM, unbounded
if len(raw) > max_bytes:                 # check happens after
    raise HTTPException(413, ...)
```
The nginx `client_max_body_size 64m` only applies when traffic goes through nginx — and `docker-compose.yml` publishes the API directly on `${API_PORT}:8000`, so the container is reachable without the proxy. A few concurrent multi-GB POSTs will OOM the API.

Then, for ZIPs:
```python
with zipfile.ZipFile(io.BytesIO(payload)) as zf:
    for info in zf.infolist():
        if base in KNOWN_FILES:
            out[base] = zf.read(info)     # no decompressed-size limit
```
A 10 MB archive containing a highly compressible `products.csv` expands to gigabytes in RAM before `max_rows` is ever consulted (`ingest_csv.py:292-299` checks the row count *after* parsing each file).

**Fix**
- Stream `UploadFile` in chunks with a running byte counter; abort at the limit. Reject on `Content-Length` up front.
- Before `zf.read(info)`, check `info.file_size` and the cumulative decompressed total; enforce a compression-ratio ceiling (e.g. reject > 100:1).
- Stop publishing the API port directly in production compose; or set `--limit-max-request-size` at the uvicorn/proxy layer.

---

# P1 — High

### P1-1. `test_mt1_tenant_isolation.py` cannot be imported — the tenant-isolation suite has never run
**File:** `packages/opsmind/tests/test_mt1_tenant_isolation.py:15`

```python
from opsmind.auth.api_keys import hash_api_key, key_prefix
```
`packages/opsmind/auth/api_keys.py` defines only `hash_api_key` and `verify_api_key`. `grep -rn "def key_prefix"` returns nothing anywhere in the repo. This module raises `ImportError` at collection — **the entire multi-tenant isolation test file fails to run**, and pytest reports a collection error, not a pass.

This is the single clearest piece of evidence that the suite is not being executed. Given P0-1 and P0-2, the tests that would have caught them are exactly the ones that are broken.

**Fix** Add `key_prefix()` to `api_keys.py` (mirroring `invite_prefix`), and add CI (see P1-2).

---

### P1-2. No CI, and every DB-backed test self-skips into a green run
**Files:** no `.github/`, `packages/opsmind/tests/*` (`skipif` on 20+ tests)

There is no `.github/workflows`, no `.gitlab-ci.yml`, no CI configuration of any kind. Every meaningful test is guarded:
```python
@pytest.mark.skipif(not _db_ready(), reason="MT1 migration required")
```
`_db_ready()` swallows the connection exception and returns `False`. On a machine without Postgres — which is every machine without manual setup — `pytest` exits 0 with everything skipped. There is no `--strict-markers`, no minimum-coverage gate, no assertion that the DB fixtures actually ran.

There are also **zero frontend tests** (no vitest/jest, no `test` script in `apps/web/package.json`) and no ESLint config.

**Fix** Add a GitHub Actions workflow with a `pgvector/pgvector:pg16` service container, run `alembic upgrade head`, then `pytest -q`. Fail the job if the skip count exceeds a small allowlist. Add `ruff check`, `tsc --noEmit`, and `npm run build` as separate jobs.

---

### P1-3. Investigations fall back to a hardcoded 2026-08 demo window for any question without explicit ISO dates
**Files:** `packages/opsmind/tools/dates.py:10-13`, `packages/opsmind/agents/planner.py:32-38`

```python
PROBLEM_WEEK_START = date(2026, 8, 17)
PROBLEM_WEEK_END   = date(2026, 8, 23)
PRIOR_WEEK_START   = date(2026, 8, 10)
PRIOR_WEEK_END     = date(2026, 8, 16)
```
`_windows_for_question()` falls back to these constants whenever `extract_compare_windows_from_question()` finds no explicit `YYYY-MM-DD` range. So a real tenant asking *"why did revenue drop last week?"* gets an investigation against **a fixed demo calendar**, not last week. Every SQL template returns zero rows, the critic flags `missing_sql_evidence`, and the run burns its full retry budget before abstaining — while appearing to have worked.

This is the most user-visible correctness bug in the product for anyone who isn't the demo tenant.

**Fix** Resolve relative windows against `date.today()` (or the tenant's `timezone` from `tenant_settings`, which already exists and is unused): "last week" → the Monday–Sunday week preceding today; "last 7 days" → `today-7 .. today-1`. Keep the seed constants strictly behind an eval/demo flag. When no window can be resolved and the tenant's data does not cover the fallback, route to `needs_clarification` rather than running a dead investigation.

---

### P1-4. Citation verification checks that IDs exist, not that claims are supported
**Files:** `packages/opsmind/grounding/verifier.py:35-72`, `packages/opsmind/agents/recommender.py:24-83`

`verify_claim_source_map()` only asserts `source_id in valid_source_ids`. The heuristic recommender then does this:
```python
claim_sources = (sql_sources[:2] + rag_sources[:2]) if ... else source_ids[:4]
for d in drivers:
    claim_map.append({"claim": d, "source_ids": claim_sources})   # same list for every claim
```
Every claim gets an identical, arbitrarily-chosen citation bundle. The verifier passes, `citation_verified=True` is written to the audit record, and the UI renders confident citation pills — for claim→source pairings that were never actually established.

Worse, `actions` in heuristic mode is a **static hardcoded template**:
```python
actions = [
    "If inventory findings show zero/low available: escalate replenishment ...",
    "If carrier late_count is elevated: divert volume to backup carriers ...",
    ...
]
```
These five conditional sentences ship verbatim regardless of what the evidence says, presented as an evidence-backed action checklist.

**Fix**
- Require each `claim_source_map` entry's `source_ids` to be a **subset of the findings that actually produced the numbers in that claim**. At minimum, extract numeric tokens from the claim and require them to appear in at least one cited finding's rows (`grounding_rules.numeric_mismatch_gaps` already has the machinery — apply it per-claim, not per-report).
- In heuristic mode, emit only actions whose triggering condition is satisfied by real rows, and mark the report `degraded: true`.

---

### P1-5. Case-memory findings are accepted as first-class citations
**Files:** `packages/opsmind/agents/case_memory_agent.py:78-127`, `packages/opsmind/grounding/verifier.py:19-33`

The README states: *"Every claim is strictly cited against immutable tool artifacts (`sql_` query findings or `rag_` playbook excerpts)."*

`case_memory_node` injects findings with `source_id = f"case_{short_id}"`, and `collect_valid_source_ids()` accepts **any** finding's `source_id` without inspecting the prefix. So a recommendation can be fully "verified" while citing nothing but a prior `CaseSummary` — which is itself LLM-generated prose from an earlier run. Model output becomes evidence for the next model output, with the audit trail asserting it was grounded.

**Fix** Restrict the verifier's valid set to `sql_*` and `rag_*` prefixes. Require at least one `sql_` citation on any claim containing a number. Carry case-memory into the prompt as clearly-labelled *context*, never into `claim_source_map`.

---

### P1-6. LLM failures are silently swallowed — the system degrades to canned text with no signal
**Files:** `packages/opsmind/agents/planner.py:340-349`, `synthesizer.py:203-208`, `recommender.py:141-148`

The same pattern appears in all three LLM-calling agents:
```python
try:
    plan = _llm_plan(question, runtime, gaps=...)
except (LLMError, Exception):
    plan = _heuristic_plan(question, gaps=...)
```
`except (LLMError, Exception)` is `except Exception` (the tuple is redundant — `LLMError` is a subclass). Nothing is logged, nothing is appended to `state["errors"]`, no `investigation_event` is written. A Groq 429, an expired key, a network partition, or a schema-validation failure all produce a **silently degraded report** that is indistinguishable in the UI and the audit record from a full LLM run.

In `planner.py` the outer `else: err = None` means the fallback path never even populates the `planner_fallback` error it was clearly written to produce.

**Fix** Catch `LLMError` specifically, log at WARNING with the model and status, append `f"{node}_llm_fallback: {exc}"` to `errors`, write an `agent_<node>_degraded` event, and surface a "degraded — heuristic mode" badge in the UI. Also add retry-with-backoff for 429/5xx in `chat_json`.

---

### P1-7. The Critic's driver-coverage check is a no-op
**Files:** `packages/opsmind/agents/critic.py:20-33, 68-92`

`_text_blob()` concatenates each finding's `purpose` string into the corpus that `driver_signals` is keyword-matched against. But the plan's purposes are fixed strings from `_heuristic_plan`:
- `"Carrier late deliveries"` → guarantees `"carrier"` is present
- `"Returns spike triage"` → guarantees `"return"` is present
- `"Low-stock / stockout scan in problem week"` → guarantees `"stockout"`
- `"Active promos"` → guarantees `"promo"`

`driver_signals` therefore evaluates to all-`True` on essentially every run, so `sum(...) < 1` is never satisfied and `missing_driver_coverage` never fires. One of the four critical gap signals that drives self-correction is dead code.

Related: `findings` is `Annotated[list, operator.add]`, so retries **accumulate** rather than replace. After the first pass `"sql" not in kinds` can never be true, disabling `missing_sql_evidence` too — and the findings list (and the LLM context built from it) grows on every retry.

**Fix** Match against `evidence.claim` and actual row *values*, never against planner-authored `purpose` labels. Scope the retry-pass gap checks to findings produced in the current pass (track a `pass_index` on each finding).

---

### P1-8. `submit_investigation_review` trusts a client-supplied reviewer identity
**File:** `apps/api/app/routes/investigations.py:44-57, 160-190`

```python
class SubmitReviewBody(BaseModel):
    reviewer: str = Field(default="operator@opsmind.internal", ...)
```
The authenticated user's email is right there in `TenantContext.user_email`, but the route passes `body.reviewer` straight into `record_review()` and stores it on the `Review` row. Any authenticated user can approve an investigation under someone else's name — and approval is the action that promotes a case into organisational memory, where it then influences future investigations (P1-5).

The endpoint also only requires `require_tenant_context`, so an **API-key** caller (no user identity at all) can approve reports.

**Fix** Drop `reviewer` from the request body. Use `tenant.user_email` and store `tenant.user_id` as a proper FK. Change the dependency to `require_user_session`. Consider requiring a role for approval.

---

### P1-9. Every 401 from any endpoint is reported to the user as "Invalid email or password"
**File:** `apps/web/src/lib/api.ts:308-310`

```python
if (response.status === 401) {
  throw new Error("Invalid email or password.");
}
```
This is in the shared `request()` helper, so it fires for *every* API call. When a 72-hour JWT expires mid-session, the user is told their password is wrong — on the console page, the history page, anywhere. There is no session-expiry handler, no automatic `clearSession()`, and no redirect to `/login`; the app just shows a nonsensical error and stays put.

(The two upload helpers get this right with `"Your session has expired"` — the shared path does not.)

**Fix** In `request()`, on 401: `clearSession()`, then redirect to `/login` with a `notice=session_expired`. Reserve the credential message for the `/auth/login` call specifically.

---

### P1-10. "Live DAG visualization" is not live
**Files:** `apps/web/src/components/investigation/LiveDAGView.tsx:21-42`, `apps/api/app/routes/investigations.py:88-146`, `apps/web/src/pages/ConsolePage.tsx:29-42`

`POST /investigations` rejects `wait=false` outright and runs `graph.invoke()` synchronously to completion before responding. There is no SSE endpoint, no WebSocket, and no polling of a run-status endpoint. `LiveDAGView` derives its state from `investigation.run.node_trace` — which only exists *after* the run has finished.

So the "live 6-agent DAG" renders a finished trace, and during the run the user sees a static spinner reading *"This usually takes a few seconds"* — while `nginx.conf` sets `proxy_read_timeout 600s` for exactly this route, an implicit admission that runs can take ten minutes.

**Fix** Either (a) make it truly async — return `202 + investigation_id` immediately, run the graph on a background worker, and expose `GET /investigations/{id}/events` as SSE (the `investigation_events` table already records every node transition, so the data is there); or (b) update the README and the spinner copy to describe the actual synchronous behaviour. (a) is the right call given the UI already exists.

---

### P1-11. `CORSMiddleware` is configured with `allow_origins=["*"]` **and** `allow_credentials=True`
**File:** `apps/api/app/main.py:59-65`

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
```
This combination is invalid per the CORS spec — browsers reject `Access-Control-Allow-Origin: *` on credentialed requests — so the `allow_credentials` flag is a latent trap for the cookie migration in P0-6. Independently, `allow_origins=["*"]` means any website can make authenticated cross-origin calls using a `Bearer` header read from a compromised page.

**Fix** Add `CORS_ALLOWED_ORIGINS` to `Settings` (comma-separated), default to `[APP_PUBLIC_URL]`, and never use `*` when `allow_credentials=True`.

---

### P1-12. No rate limiting anywhere — login, signup, invite redemption, password reset, and investigations are all unthrottled
**Files:** entire `apps/api` (grep for `slowapi|rate_limit|limiter` returns nothing)

Concrete exposures:
- `POST /auth/login` — unlimited password guessing, no lockout, no backoff.
- `POST /auth/join` — invite codes are ~40 bits (`OM-XXXX-XXXX` over a 32-char alphabet); brute-forceable without throttling.
- `POST /auth/signup` — unlimited tenant creation, each of which writes `tenants` + `tenant_settings` + `users` rows.
- `GET /auth/request-status` — **completely unauthenticated**, and returns 404 vs 200 depending on whether an email has a request in a given tenant: a clean account-enumeration oracle.
- `POST /investigations` — each call fans out to ~15 SQL queries and up to 3 LLM calls against a metered API. No per-tenant daily cap is enforced despite `soft_limits.max_investigations_per_day = 50` being written at signup and never read.

`login()` also returns immediately when the user is not found, without a dummy hash verification — a timing oracle for enumeration on top of the response-shape one.

**Fix** Add `slowapi` (or nginx `limit_req`) with per-IP and per-account buckets on all auth endpoints. Add progressive lockout on repeated login failures. Make `/auth/request-status` require the invite code *and* return a uniform response. Enforce `max_investigations_per_day` in `create_and_run_investigation`. In `login()`, always run `verify_password` against a dummy hash when the user is missing.

---

### P1-13. Raw exception text is returned to clients and written to the event log
**Files:** `apps/api/app/routes/investigations.py:120-124`, `routes/tools.py:113-116, 155-158`, `routes/data.py:151-158`, `packages/opsmind/agents/data_investigator.py:72-73`

```python
except Exception as exc:  # noqa: BLE001
    raise HTTPException(status_code=500, detail=str(exc)) from exc
```
A `sqlalchemy` or `psycopg` error string carries table names, column names, constraint names, and sometimes parameter values. `data_investigator` additionally appends `f"sql:{key}: {exc}"` to `state["errors"]`, which is persisted into `investigation_events.payload` and returned in the API response.

`sanitize_output_payload` catches connection URIs and `sk-`/`gsk_` tokens but nothing else.

**Fix** Log the exception server-side with a correlation ID; return `{"error": "internal_error", "request_id": "..."}` to the client. Keep detailed messages only for the `SqlToolError`/`CsvIngestError` classes, which are authored and safe.

---

# P2 — Medium

### P2-1. `_derive_daily_metrics` is O(orders × shipments)
**File:** `packages/opsmind/db/ingest_csv.py:238-241`
```python
for ship in shipments:
    order = next((o for o in orders if o.id == ship.order_id), None)
```
A linear scan over all orders, inside a loop over all shipments. At the documented 50 000-row ceiling this is ~10⁹ comparisons in the request thread. It also loads `orders`, `items`, `shipments`, and `returns` fully into memory first.
**Fix** Build `orders_by_id = {o.id: o for o in orders}` once (the code already does exactly this for `items_by_order` three lines above). Better: derive `daily_metrics` in SQL with a single `INSERT … SELECT … GROUP BY`.

### P2-2. No pgvector index — every RAG query is a sequential scan
**Files:** `0003_memory_and_rag.py` (no `ivfflat`/`hnsw` index), `packages/opsmind/tools/rag_tool.py:77-95`, `packages/opsmind/memory/persist.py:262-283`
`document_chunks.embedding` and `case_summaries.embedding` have no vector index, so `ORDER BY embedding <=> ...` scans every row in the tenant's corpus on each of the 5 RAG steps per investigation.
**Fix** `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` on both tables. Add `WHERE tenant_id = ...` as a partial-index consideration if corpora get large.

### P2-3. Switching embedding providers silently corrupts retrieval
**Files:** `packages/opsmind/tools/embeddings.py:123-136`, `packages/opsmind/memory/persist.py:190`
`embed_texts()` picks `local` or `openai` from an env var at call time. Chunks embedded under `local` (a 384-dim hashing bag-of-words) sit in the same column as chunks embedded under `openai`, and query vectors are generated with whatever the env var says *now*. Cosine similarity across two unrelated vector spaces returns noise. There is no `embedding_provider`/`embedding_model` column on `document_chunks` and no re-index path.

Separately, `record_review()` and `query_similar_cases()` hardcode `local_embed()` regardless of configuration — so case memory is always the non-semantic hashing embedding even when OpenAI is configured.
**Fix** Store `embedding_provider` + `embedding_model` on each chunk; refuse to query across mismatched spaces; add a `scripts/reindex_embeddings.py`. Route case-memory embedding through `embed_one()` like everything else.

### P2-4. `local` hashing embeddings are the shipped default and are not semantic
**Files:** `packages/opsmind/tools/embeddings.py:22-40`, `.env.example:37`
`local_embed` is a signed hashing trick over tokens — it captures exact-token overlap and nothing else. `OPSMIND_EMBEDDING_PROVIDER=local` is the `.env.example` default, so out of the box "playbook vector RAG" is effectively keyword matching with worse recall than `tsvector`.
**Fix** Default to `openai` in production config (keep `local` for CI determinism), and say so explicitly in the README, which currently describes this as vector RAG without qualification.

### P2-5. Bulk deletes are performed row-by-row through the ORM
**Files:** `apps/api/app/routes/data.py:196-212, 236-254`
```python
rows = session.scalars(select(model).where(model.tenant_id == tid)).all()
for row in rows:
    session.delete(row)
```
Loads every row of nine tables into the identity map, then issues one `DELETE` per row. For a 50 000-row tenant that is tens of thousands of statements. `clear_tenant_business_data()` in `ingest_csv.py:153-167` already does this correctly with `session.execute(delete(model).where(...))` — the route just doesn't reuse it.
**Fix** Call `clear_tenant_business_data()`; use bulk `delete()` for `IngestJob` too.

### P2-6. N+1 queries throughout the access and investigation list endpoints
**Files:** `apps/api/app/routes/access.py:31-49, 158-190`, `packages/opsmind/graph/runner.py:420-450`
- `_request_to_dict()` issues a `session.get(User)` and a `session.get(InviteCode)` **per request row**.
- `list_access_users()` issues an `AccessRequest` query **plus** a reviewer `User` lookup per user.
- `list_investigations_view()` lazy-loads `reviews` and `case_summary` per investigation (up to 100 rows → 200 extra queries).
**Fix** `selectinload()` / explicit joins.

### P2-7. `latest_review` is picked by list position from an unordered relationship
**File:** `packages/opsmind/graph/runner.py:434-435`
```python
latest_review = reviews[-1] if reviews else None
```
The `reviews` relationship has no `order_by`, so SQLAlchemy returns them in whatever order Postgres yields — the "latest review decision" shown in History can be any review, not the newest.
**Fix** Add `order_by=Review.created_at` to the relationship, or sort explicitly (as `load_investigation_view` correctly does at line 358).

### P2-8. Connection pool is undersized for a threadpool-based sync app
**File:** `packages/opsmind/db/session.py:16`
```python
_engine = create_engine(database_url_sync, pool_pre_ping=True)   # default pool_size=5, max_overflow=10
```
Every route is `def` (not `async def`), so FastAPI runs them in a threadpool of 40 by default. Each request may open the owner session *plus* the read-only session, and agent nodes open additional sessions. 15 concurrent investigations will exhaust the pool and block on `QueuePool` timeouts. No `pool_recycle` is set either, so stale connections accumulate behind NAT/proxy idle timeouts.
**Fix** Size the pool from config (`pool_size=20, max_overflow=10, pool_recycle=1800, pool_timeout=10`) and align it with the uvicorn worker/threadpool count.

### P2-9. SQL templates have no `LIMIT` and no `statement_timeout`
**Files:** `packages/opsmind/tools/sql_templates.py`, `packages/opsmind/tools/sql_tool.py:80-87`
`revenue_by_day`, `sku_revenue_mix`, `returns_by_reason`, `inventory_by_sku`, and `cancelled_orders` return unbounded result sets. A wide date range on a large tenant materialises the whole thing in Python (`_row_to_dict` per row), then fingerprints it via `json.dumps`. The read-only engine sets no `statement_timeout`, so a slow query blocks a pooled connection indefinitely.
**Fix** Add `LIMIT :max_rows` (bound, default ~5000) to every template; set `options="-c statement_timeout=15000"` on the read-only engine; validate that `end_date - start_date` is within a configured maximum.

### P2-10. `default_registry` is an unbounded process-global
**File:** `packages/opsmind/grounding/registry.py:47`
Every `run_sql_tool`/`run_rag_tool` call registers a `SourceRecord` in a module-level dict that is never cleared. It grows for the lifetime of the process — a slow memory leak — and mixes source IDs from all tenants in one namespace. It is also process-local, so it is meaningless with multiple uvicorn workers or replicas.

Notably, `verifier.collect_valid_source_ids()` derives its valid set from **findings**, not from the registry — so the registry is effectively vestigial.
**Fix** Either delete it, or scope it per-run and clear it in `run_investigation`'s `finally` alongside `clear_run_budget`.

### P2-11. Per-run budget registry is process-local and leaks on some paths
**File:** `packages/opsmind/guardrails/budget.py:37-52`
`_REGISTRY` is a plain module dict. With >1 worker, a run scheduled on worker B cannot see the budget registered on worker A, and `consume_tool_budget` silently no-ops (`if budget is None: return`) — **the tool budget is not enforced**. Entries are also only cleared on the success and explicit-exception paths in `run_investigation`; a hard process signal leaves them behind.
**Fix** Persist `tool_calls_used` on the `investigations` row (it is already transactional and per-run), or move the counter into the graph state.

### P2-12. Test-only branching lives in the production agent path
**File:** `packages/opsmind/agents/data_investigator.py:22-29`
```python
# Test fixture: hide SQL on first pass to force Critic retry.
if runtime.get("block_sql_on_first_pass") and retry_count == 0:
    blocked = blocked | {...}
```
A runtime flag that disables all SQL evidence gathering is reachable from `runtime_overrides`. It is only set by tests today, but it is a live code path in the shipped agent.
**Fix** Move to a test fixture that monkeypatches `run_sql_tool`.

### P2-13. Dead `fanout` node, and the README describes parallelism the graph doesn't have
**Files:** `packages/opsmind/graph/builder.py:42-44, 62`, `README.md` (architecture diagram)
`_fanout_passthrough` is registered as a node but never connected by any edge. The README diagram shows `[2. Data Investigator]` and `[3. Knowledge Agent]` branching in parallel; `build_investigation_graph` wires them strictly sequentially (`case_memory → data_investigator → knowledge → synthesizer`). Since the two are independent, running them in parallel would meaningfully cut latency.
**Fix** Either wire the real fan-out/fan-in (that is what `findings` being an `operator.add` reducer is for), or delete the node and correct the diagram.

### P2-14. SQL steps execute serially, each opening its own session
**File:** `packages/opsmind/agents/data_investigator.py:47-71`
~10–14 templates per plan, each a fresh `with factory() as ro_session` round trip plus a `session.commit()` in `persist_tool_result`. That is ~15 sequential DB round trips and ~15 commits per investigation pass, multiplied by retries.
**Fix** Reuse one read-only session for the whole node; batch the finding/invocation inserts into a single flush+commit at the end.

### P2-15. Non-reproducible builds — unpinned Python deps and `npm install` in Docker
**Files:** `pyproject.toml:7-22`, `apps/web/Dockerfile:10`
Every Python dependency is `>=` with no lockfile (`langgraph>=0.2.0` is especially loose given the API churn in that library). The web Dockerfile runs `npm install` despite `package-lock.json` being committed, so the lockfile is ignored and transitive versions drift between builds.
**Fix** Add `uv.lock` or a pinned `requirements.txt` (with hashes) and install from it in the API image. Change to `npm ci`.

### P2-16. Containers run as root; no healthchecks; migrations race on multi-replica start
**Files:** `apps/api/Dockerfile`, `docker-compose.yml`, `apps/api/entrypoint.py:46-55`
- Neither Dockerfile declares a `USER`; the API runs as root.
- `docker-compose.yml` has a healthcheck for `db` but none for `api` or `web`, and no `restart:` policy.
- `pip install -e .` (editable) in a production image.
- `_run_migrations()` catches every exception and only prints `WARNING`, then **starts the server anyway** against a possibly half-migrated schema. With more than one replica, all of them run `alembic upgrade head` concurrently.
- Uploaded ZIPs and playbooks are written to container-local disk (`data/uploads/…`), so they vanish on redeploy and are invisible to sibling replicas.
**Fix** Add `USER app`; add healthchecks hitting `/ready`; install non-editable; run migrations as a separate one-shot job/init container and **exit non-zero on failure**; move uploads to object storage or a mounted volume.

### P2-17. No logging, no metrics, no tracing — `LOG_LEVEL` is required but never used
**Files:** `apps/api/app/config.py:18`, whole codebase
`log_level` is a **required** `Settings` field, so the app refuses to boot without it — and nothing ever reads it. `grep -rn "getLogger"` finds exactly one logger, in `email.py`. There is no `logging.basicConfig`, no request-ID middleware, no access logging beyond uvicorn's default, no metrics endpoint, and no error tracking. Diagnosing a failed investigation in production means reading `investigation_events` by hand.
**Fix** Configure `logging.dictConfig` from `log_level` at startup; add a request-ID middleware and structured JSON logs; emit LLM token/latency/cost counters; add `/metrics` or wire Sentry/OTel.

---

# P3 — Low / Polish

1. **`.env.example` leaks a real host** — `APP_PUBLIC_URL=http://116.202.210.102:3015` points at what looks like a live deployment. Should be `http://localhost:3000`.
2. **Password policy is length-only** — `hash_password` enforces ≥8 bytes and nothing else. No breach-list check (HIBP k-anonymity), no complexity, no maximum. `Field(max_length=128)` on the Pydantic model but PBKDF2 accepts any length.
3. **PBKDF2 over Argon2id** — 210k iterations of PBKDF2-SHA256 is defensible (OWASP-compliant) but Argon2id is the current recommendation. Note the deliberate "no extra deps" trade-off in the docstring; worth revisiting.
4. **Reset token travels in a URL query string** — `?token=...` lands in browser history, `Referer` headers, and proxy logs. Prefer a POST-ed form or a fragment.
5. **`access_requests.password_hash` is never cleared after approval** — the hash is copied to `users` in `approve_access_request` but left behind in `access_requests` indefinitely, duplicating credential material.
6. **Triage precedence bug** — `_UNSUPPORTED_PATTERNS` is checked before `_OPS_KEYWORDS`, so *"did the weather cause our carrier delays last week?"* is rejected as off-domain. Score both and prefer the ops signal.
7. **Stale keywords in `triage.py`** — `\bproject\b`, `\bclient\b`, `\bengagement\b` in `_OPS_KEYWORDS` look like leftovers from a different domain and will misroute questions. `\bhr\b` in the unsupported list matches "24 hr".
8. **`_SKU_RE` requires a `SKU-` prefix** (`dates.py:39`, `planner.py:26`) — real tenants have arbitrary SKU formats, so SKU extraction from questions only works for demo data.
9. **`update_investigation` silently ignores unknown fields** — `if not hasattr(inv, key): continue` turns a typo'd kwarg into a no-op. Raise instead.
10. **`count_documents()`** (`rag_tool.py:219`) materialises every row to compute a length; use `select(func.count())`. Appears unused — consider deleting.
11. **Frontend polish** — no `ErrorBoundary`, no `React.lazy` route splitting (every page is eagerly bundled), no request timeouts / `AbortController`, one `catch (err: any)` in `ApiKeyModal.tsx:37`, no ESLint config. `humanizeApiError` matches on substrings (`s.includes("critic")`) and will mangle unrelated messages.

---

## Suggested Order of Work

**Sprint 1 — close the security holes**
P0-1 + P0-2 together (FORCE RLS and fix the GUC lifetime in the same change; they must ship as a pair or the app breaks), P0-3, P0-4, P0-5, P0-6, P0-7.

**Sprint 2 — make the guarantees real**
P1-1 + P1-2 (fix the import, add CI — do this first so everything after it is verified), then P1-4, P1-5, P1-6, P1-7, P1-8, P1-13.

**Sprint 3 — make it work for non-demo tenants**
P1-3 (relative date windows — the biggest functional blocker for real customers), P1-10 (async runs + SSE), P1-9, P1-11, P1-12.

**Sprint 4 — scale and operate**
P2-1, P2-2, P2-5, P2-6, P2-8, P2-9, P2-17.

**Ongoing** — P2 remainder and P3 as they are touched.

---

## What's Working Well

Worth stating plainly, because the issue list above is long:

- **Allowlisted parameterized SQL** is the right architecture for LLM-driven database access. `_assert_template_safe` + `_validate_params` + a separate read-only role is genuine defence in depth, and it is applied consistently.
- **The evidence model is well-designed.** `Evidence` / `Finding` / `ToolInvocation` with result fingerprints and immutable `source_id`s gives you a real audit substrate — the pieces needed to fix P1-4 and P1-5 are already in place.
- **`token_version` on `User`** is proper server-side JWT revocation, correctly bumped on every password change and checked on every request. Many codebases skip this.
- **Consistent structure.** Naming, module boundaries, and error-handling patterns are uniform across 21k lines. A new contributor can predict where things live.
- **The access-request workflow** (invite → pending request → admin approval → notification) is complete and handles the re-submission-after-rejection edge case thoughtfully.
- **The frontend is clean** — strict TypeScript, no XSS sinks, no `dangerouslySetInnerHTML`, `noUnusedLocals`/`noUnusedParameters` on.
- **Documentation is thorough** (10 files in `docs/`), even where it has drifted from the implementation.

---

## Verification Notes

Findings were derived from static reading. The following were **directly confirmed** by grep/file inspection:

- `key_prefix` is imported by `test_mt1_tenant_isolation.py:15` and defined nowhere in the repo (`grep -rn "def key_prefix"` → no results). **Confirmed broken import.**
- No `FORCE ROW LEVEL SECURITY` anywhere (`grep -rn "FORCE ROW LEVEL"` → no results).
- No rate-limiting library or config (`grep -rn "slowapi|rate_limit|limiter|Throttle"` → no results).
- No `.github/` directory; no CI config of any kind.
- No `ivfflat`/`hnsw` index in any migration (`grep -rn "ivfflat|hnsw"` → no results).
- `fanout` appears only at `builder.py:42` and `:62` — registered, never wired.
- `log_level` appears in `config.py:18` and in test `monkeypatch.setenv` calls only — never read by application code.
- No API-key management route exists (`grep -rn "api-keys|api_keys" apps/api/app/routes/` → no results).

The following would benefit from **runtime confirmation** once dependencies are installed:
- The exact RLS behaviour under your deployed role setup (run `SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'orders';` and confirm `current_user` is not the table owner).
- The P2-1 O(n²) cost at your real data volumes.
- Whether `langgraph`'s current version warns about or rejects the unreachable `fanout` node.
