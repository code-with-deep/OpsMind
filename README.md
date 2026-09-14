# OpsMind

**Self-Correcting Multi-Agent Operations Intelligence System** for ecommerce, warehouse, and supply-chain operations.

OpsMind investigates complex operational anomalies, gathers evidence from business databases and standard operating procedure (SOP) playbooks, critiques its own conclusions, self-corrects when evidence is weak, and returns an evidence-backed recommendation for human operators.

> **Grounding Principle:** Not a generic chatbot. Every claim is strictly cited against immutable tool artifacts (`sql_` query findings or `rag_` playbook excerpts). If evidence is insufficient, OpsMind abstains (*cite-or-abstain*).

---

## Current Status & Phase Completion

All implementation phases **P0 through P8** are 100% complete, verified, and benchmarked:

- **P0 Foundation**: FastAPI application, PostgreSQL (Supabase) with `pgvector`, and Alembic database migrations.
- **P1 Business Data**: Realistic ecommerce/warehouse schema (orders, shipments, inventory, returns), deterministic seed data, planted failure scenarios, and a restricted read-only SQL role.
- **P2 Tools & Evidence**: Allowlisted parameterized SQL query templates, ISO/alias date normalizer, playbook vector RAG with heading-aware chunking, and immutable `SourceIdRegistry`.
- **P3 Multi-Agent LangGraph**: 6 specialized agents (*Planner*, *Data Investigator*, *Knowledge Agent*, *Synthesizer*, *Critic*, *Recommender*) orchestrated as a stateful LangGraph workflow with PostgreSQL checkpointer.
- **P4 Self-Correction & Grounding**: Automated Critic evaluation loop with dynamic replanning (up to 2 retries), citation verifier, and cite-or-abstain routing.
- **P5 Security & Guardrails**: API key authentication (`X-API-Key`), zero-trust input safety filters (prompt-injection / jailbreak defense), output PII redaction, tool execution budgets, and cryptographic audit logging.
- **P6 Operator Console & Case Memory**: Modern, fully responsive React 19 + TypeScript + Tailwind CSS web console featuring interactive product landing page, live 6-agent DAG visualization, timeline telemetry, evidence explorer, and human-in-the-loop review with episodic vector case memory.
- **P7 Evaluation Harness**: Golden evaluation benchmark dataset (`evals/cases.jsonl`), automated scoring engine (faithfulness, numeric accuracy, abstention recall, adversarial robustness), and CLI test runner (`docs/EVAL_BASELINE.md`).
- **P8 Production Polish & Demo Walkthrough**: End-to-end operational incident demo scripts (`docs/DEMO_SCRIPT.md`), runbooks, and performance verification.

---

## Key Capabilities & Architecture

```text
[User / Incident Alert]
         │
         ▼
[0. Security Guardrails] ── (Prompt Injection / Malicious Jailbreak Check)
         │ (Passed)
         ▼
[1. Planner & Triage] ──── (Time Normalization, Domain Bounds, Case Memory Retrieval)
         │
    ┌────┴──────────────────────────┐
    ▼                               ▼
[2. Data Investigator]     [3. Knowledge Agent]
(Allowlisted Read-Only SQL) (pgvector SOP Playbook RAG)
    └────┬──────────────────────────┘
         ▼
[4. Synthesizer] ───────── (Hypothesis Formulation, Driver Mix, Confidence Scoring)
         │
         ▼
[5. Critic Self-Correction] ◄─── (Evidence Breadth & Gap Verification)
         │
         ├─── [Decision: Retry (Gap Detected)] ──► Re-routes to Planner (max 2 retries)
         │
         └─── [Decision: Pass (Grounded)]
                   │
                   ▼
         [6. Recommender] ─── (Citation Verification & Action Checklist)
                   │
                   ▼
     [Human Operator Review] ── (Approve / Reject ──► Vector Case Memory)
```

### 6 Specialized Agents in LangGraph

| Agent | Responsibility | Backing Technology |
| :--- | :--- | :--- |
| **Planner & Triage** | Validates question domain, normalizes date expressions to ISO, and retrieves relevant case memory. | Groq LLM / Heuristic Regex Fallback |
| **Data Investigator** | Executes parameterized read-only SQL templates against orders, shipments, returns, and inventory. | Restricted PostgreSQL Role |
| **Knowledge Agent** | Searches chunked SOP playbooks for carrier routing, stockout escalation, and return procedures. | `pgvector` Cosine Similarity |
| **Synthesizer** | Merges SQL data and playbook excerpts into a multi-driver operational hypothesis with confidence rating. | Groq LLM / Deterministic Synthesizer |
| **Critic** | Evaluates hypothesis completeness and evidence breadth; commands gap-aware replanning if evidence is missing. | Rule-based & LLM Verification Loop |
| **Recommender** | Formulates prioritized operational actions with verified citations mapped to each claim. | Citation Verifier Matrix |

---

## Quick Start

OpsMind runs as two ordinary processes — the FastAPI backend and the Vite web app —
against a [Supabase](https://supabase.com/) Postgres database. No Docker required.

### Prerequisites

- [Python 3.11+](https://www.python.org/) and [Node.js 20+](https://nodejs.org/)
- A Supabase project (the free tier works)
- *(Optional)* Groq API key in `.env` as `LLM_API_KEY` — without it every agent uses its deterministic fallback.

---

### 1. Configure Environment

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

1. Supabase dashboard → **Connect → Session pooler** → copy the URI (port `5432`).
   Don't use the Transaction pooler (`6543`): live updates need LISTEN/NOTIFY.
2. In `.env` set `SUPABASE_DB_URL=<that URI>`, plus `OPSMIND_API_KEY` and `JWT_SECRET`
   (generate each with `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. Fill in the database settings (never prints your password):

```bash
.venv/bin/python scripts/configure_supabase_env.py
```

---

### 2. Create Tables and Demo Data

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m opsmind.db.seed              # demo tenant with planted incidents
.venv/bin/python -m opsmind.db.ingest_playbooks  # SOP playbooks for RAG
```

Migrations also run automatically whenever the backend starts. Migration `0018` removes
Supabase's public Data API (`anon` / `authenticated`) access to OpsMind tables.

---

### 3. Start the Backend

```bash
UVICORN_RELOAD=1 .venv/bin/python -m api.entrypoint
```

- API: [http://localhost:8000](http://localhost:8000) · Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Check: `curl http://localhost:8000/ready` → `{"status":"ready",...}`

### 4. Start the Web App (second terminal)

```bash
cd apps/web
npm install
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)**. Vite proxies every API path — including
the live-update stream `/events/stream` — to `localhost:8000`, so pages update without refreshing.

---

### 5. Tests and End-to-End Check

- **Automated tests** write data, so run them against a **disposable** Postgres with `pgvector`
  (for example a local `opsmind_test` database) — never against your Supabase project:

  ```bash
  export DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/opsmind_test
  export DATABASE_URL_SYNC=postgresql://USER:PASS@localhost:5432/opsmind_test
  export DATABASE_URL_READONLY=postgresql+asyncpg://USER:PASS@localhost:5432/opsmind_test
  DATABASE_URL_SYNC=$DATABASE_URL_SYNC .venv/bin/alembic upgrade head
  .venv/bin/python -m pytest
  ```

- **End-to-end smoke test** against the running backend (creates a throwaway test company):
  `.venv/bin/python scripts/predeploy_e2e_smoke.py` → ends with `E2E_PASS`.

---

### 6. Run Golden Evaluation Harness (P7 Benchmark)

OpsMind includes an automated evaluation harness testing 12 golden test cases across root cause analysis, abstention, vagueness, and security injection defenses:

```powershell
python -m evals.run --output-json docs/eval_results.json --output-md docs/EVAL_BASELINE.md --output-format text
```

**Evaluation Baseline Summary (`docs/EVAL_BASELINE.md`):**
- **Total Cases Tested:** 12 / 12 Passed (100% Pass Rate)
- **Status & Routing Accuracy:** 100%
- **Citation Faithfulness:** 100%
- **Theme Recall:** 100%
- **Adversarial Guardrail Robustness:** 100%

---

### 7. End-to-End Demo Script (P8)

Follow the complete step-by-step incident walkthroughs in **`docs/DEMO_SCRIPT.md`** to demo:
1. **Planted Incident #1:** Top-Seller Earbuds Stockout (`SKU-1001`)
2. **Planted Incident #2:** FastShip Carrier SLA Delay Spike
3. **Planted Incident #3:** Defective Seal Returns Spike (`SKU-1002`)
4. **Planted Incident #4:** Cable Flash Sale Cannibalization
5. **Self-Correction Demo:** Critic triggering dynamic replan retry loop
6. **Abstention Demo:** Off-domain payroll question rejected with zero hallucinations
7. **Clarification Demo:** Vague question handled with clarifying prompts
8. **Security Guardrail Demo:** Prompt injection blocked with 0 tool calls consumed
9. **Case Memory Recall:** Approved resolution embedded and retrieved in subsequent runs

---

### 8. Stop

Press `Ctrl+C` in the backend and web app terminals.

---

## Project Structure

```text
OpsMind/
├── apps/
│   ├── api/                     # FastAPI Backend Application
│   │   └── app/
│   │       ├── routes/          # API endpoints (/investigations, /tools, /cases, /reviews)
│   │       ├── auth.py          # API Key security middleware
│   │       └── main.py          # CORS, routing, and lifecycle hooks
│   └── web/                     # React 19 Operator Console & Landing Page
│       ├── src/
│       │   ├── components/      # UI components (DAG, Report, Evidence, Timeline, Cases, Modals)
│       │   ├── lib/             # API client & formatting utilities
│       │   └── types/           # TypeScript domain schemas
│       └── tailwind.config.js   # Production design system tokens
├── packages/
│   └── opsmind/                 # Core Python Operations Intelligence Engine
│       ├── agents/              # 6 LangGraph agents (Planner, Data, Knowledge, Synth, Critic, Rec)
│       ├── db/                  # SQLAlchemy models, Alembic migrations, seeding scripts
│       ├── graph/               # LangGraph StateGraph builder, runner, and checkpointer
│       ├── guardrails/          # Input injection defense & output PII redaction
│       ├── memory/              # Postgres episodic checkpointer & Case Memory vectors
│       ├── security/            # Token budgeting & SHA-256 cryptographic audit logs
│       └── tools/               # Allowlisted SQL runner & pgvector RAG retriever
├── data/
│   └── playbooks/               # Operations SOP Markdown playbooks for RAG ingestion
├── evals/                       # Automated evaluation harness (cases.jsonl, scorers, CLI runner)
├── docs/                        # Architecture specs, baseline scorecards, demo script
└── scripts/                     # Supabase env setup, sample bundles, e2e smoke test
```

---

## Database Migrations (Alembic)

| Version | Description |
| :--- | :--- |
| `0001` | Baseline schema setup (PostgreSQL + `pgvector` extension) |
| `0002` | Business tables (`products`, `inventory`, `orders`, `order_items`, `shipments`, `returns`, `carriers`, `suppliers`) |
| `0003` | Memory & Knowledge tables (`investigations`, `investigation_events`, `tool_invocations`, `findings`, `documents`, `document_chunks`) |
| `0004` | Investigation JSON report fields (`hypothesis`, `critique`, `recommendation`) |
| `0005` | Cryptographic audit trail JSONB field (`audit`) |
| `0006` | Human-in-the-loop review & episodic case memory tables (`reviews`, `case_summaries`) |
| `0007` | Multi-tenant core (`tenants`, `users`, `api_keys`, `tenant_settings` + `tenant_id` + RLS) |
| `0008` | Invite codes |
| `0009` | CSV ingest jobs (`ingest_jobs`) |
| `0016` | `opsmind_app` role so row-level security is actually enforced for tenant sessions; `pg_notify` triggers powering live console updates |
| `0017` | One-off resync of serial id sequences past existing rows |
| `0018` | Supabase: revoke public Data API (`anon`/`authenticated`) access to OpsMind tables |
| `0019` | Postgres 16+: grant the `SET` option on `opsmind_app` so tenant sessions can switch role (needed on Supabase) |

Multi-tenant onboarding (MT2–MT5): signup → invite → CSV upload → playbooks → investigate.
See `docs/MULTI_TENANT.md` and `AGENTS.md`. Demo seed data belongs to the `demo` tenant only.

---

## Documentation Index

- [Architecture & Design Decisions](docs/ARCHITECTURE.md)
- [Multi-tenant plan & status](docs/MULTI_TENANT.md)
- [E2E Operations Demo Script](docs/DEMO_SCRIPT.md)
- [Evaluation Baseline Scorecard](docs/EVAL_BASELINE.md)
- [Planted Failure Scenarios](docs/SEED_SCENARIOS.md)
- [Security & Guardrails Specification](docs/SECURITY.md)
- [Allowlisted SQL Tools](docs/TOOLS.md)
- [Self-Correction & Critic Loop](docs/SELF_CORRECTION.md)

---

## License

Private / Enterprise Operations Architecture.
