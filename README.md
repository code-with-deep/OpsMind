# OpsMind

**Self-Correcting Multi-Agent Operations Intelligence System** for ecommerce, warehouse, and supply-chain operations.

OpsMind investigates complex operational anomalies, gathers evidence from business databases and standard operating procedure (SOP) playbooks, critiques its own conclusions, self-corrects when evidence is weak, and returns an evidence-backed recommendation for human operators.

> **Grounding Principle:** Not a generic chatbot. Every claim is strictly cited against immutable tool artifacts (`sql_` query findings or `rag_` playbook excerpts). If evidence is insufficient, OpsMind abstains (*cite-or-abstain*).

---

## Current Status & Phase Completion

All implementation phases **P0 through P8** are 100% complete, verified, and benchmarked:

- **P0 Foundation**: FastAPI application, Docker Compose stack, PostgreSQL 16 with `pgvector`, and Alembic database migrations.
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

### Prerequisites

- [Docker Desktop](https://www.docker.com/) (or Docker Engine + Compose v2+)
- [Node.js 20+](https://nodejs.org/) & `npm`
- [Python 3.11+](https://www.python.org/)
- *(Optional)* Groq API key in `.env` as `LLM_API_KEY` (system features built-in deterministic fallback heuristics for all agents when no LLM key is provided).

---

### 1. Configure Environment

```powershell
# In project root
Copy-Item .env.example .env

# Optional: Add your Groq API key for LLM-backed Planner/Synthesizer/Recommender
# Set OPSMIND_API_KEY (default: change-me-opsmind-dev-key)
```

---

### 2. Start the Stack with Docker Compose

```powershell
docker compose up --build -d
```

---

### 3. Apply Migrations, Seed Incident Data, and Ingest Playbooks

```powershell
# Run database migrations
docker compose exec api alembic upgrade head

# Seed planted operational incidents (Earbuds stockout, FastShip SLA delays, Thermostat returns)
docker compose exec api python -m opsmind.db.seed

# Ingest and vector-embed SOP markdown playbooks
docker compose exec api python -m opsmind.db.ingest_playbooks
```

---

### 4. Verify API & Service Health

```powershell
# Health check
curl http://localhost:8000/health

# Readiness check (DB & Vector store)
curl http://localhost:8000/ready

# List allowlisted SQL templates (Requires API key header)
curl -H "X-API-Key: change-me-opsmind-dev-key" http://localhost:8000/tools/sql/templates
```

---

### 5. Launch the Operator Web Console (Frontend)

Run the responsive Vite development server:

```powershell
cd apps/web
npm install
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser to:
- Browse the interactive **Product Overview & Story Landing Page**.
- Launch live multi-agent investigations on the **Operator Console**.
- Visualize real-time LangGraph DAG execution flow and Critic retry loops.
- Explore cited evidence with SQL sample tables and SOP playbook excerpts in the **Evidence Explorer**.
- Submit human-in-the-loop approvals to store episodic vector embeddings in **Case Memory**.
- Test and inspect allowlisted queries in the **SQL Tools Lab**.

*Interactive API Swagger Documentation:* **[http://localhost:8000/docs](http://localhost:8000/docs)**

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

### 8. Stop the Stack

```powershell
docker compose down
```

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
└── docker-compose.yml           # Multi-container orchestration (api, db, web)
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

---

## Documentation Index

- [Architecture & Design Decisions](docs/ARCHITECTURE.md)
- [E2E Operations Demo Script](docs/DEMO_SCRIPT.md)
- [Evaluation Baseline Scorecard](docs/EVAL_BASELINE.md)
- [Planted Failure Scenarios](docs/SEED_SCENARIOS.md)
- [Security & Guardrails Specification](docs/SECURITY.md)
- [Allowlisted SQL Tools](docs/TOOLS.md)
- [Self-Correction & Critic Loop](docs/SELF_CORRECTION.md)

---

## License

Private / Enterprise Operations Architecture.
