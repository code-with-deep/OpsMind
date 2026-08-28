# OpsMind

**Self-Correcting Multi-Agent Operations Intelligence System** for ecommerce / warehouse operations.

OpsMind investigates operational questions, gathers evidence from business data and playbooks, critiques its own conclusions, self-corrects when evidence is weak, and returns an evidence-backed recommendation for a human operator.

> Not a chatbot. Claims must be grounded in tool evidence (cite-or-abstain).

## Current status

**Phase 5 — Security, guardrails, auth** complete: API key auth on `/investigations` and
`/tools`, input/output guardrails, RAG sanitization, per-run tool budgets, terminal audits.

## Quick start

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2+)
- Git
- Optional: Groq API key in `.env` as `LLM_API_KEY` (heuristic agents work without it)

### 1. Environment file

```powershell
cd "d:\PROJECTS\AI Projects\OpsMind"
Copy-Item .env.example .env
# Set LLM_API_KEY if you want Groq-backed Planner/Synthesizer/Recommender
# Set OPSMIND_API_KEY (required for /investigations and /tools)
```

### 2. Start the stack

```powershell
docker compose up --build -d
```

### 3. Migrate + seed + ingest playbooks

```powershell
docker compose exec api alembic upgrade head
docker compose exec api python -m opsmind.db.seed
docker compose exec api python -m opsmind.db.ingest_playbooks
```

See `docs/SEED_SCENARIOS.md`, `docs/TOOLS.md`, `docs/INVESTIGATIONS.md`,
`docs/SELF_CORRECTION.md`, and `docs/SECURITY.md`.

### 4. Smoke checks

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/ready

# Tools require API key (from .env OPSMIND_API_KEY)
curl -H "X-API-Key: change-me-opsmind-dev-key" http://localhost:8000/tools/sql/templates
```

Run an investigation (PowerShell):

```powershell
$headers = @{ "X-API-Key" = "change-me-opsmind-dev-key"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method POST http://localhost:8000/investigations `
  -Headers $headers `
  -Body '{"question":"Why did our revenue decrease this week (2026-08-17 to 2026-08-23), and what should we do?"}'
```

API docs: http://localhost:8000/docs

### 5. Stop

```powershell
docker compose down
```

## Layout

```text
apps/api/           FastAPI (+ auth, /tools, /investigations)
apps/web/           Operator UI (Phase 6)
packages/opsmind/   db, tools, agents, graph, guardrails, domain, memory, grounding
data/playbooks/     SOP markdown for RAG
evals/              Golden evals (Phase 7)
docs/               Architecture and runbooks
docker-compose.yml  api + db
alembic.ini         Migration config
```

## Migrations (Alembic)

- `0001` empty baseline (P0)
- `0002` business tables (P1)
- `0003` memory + documents/embeddings (P2)
- `0004` investigation report JSON fields (P3)
- `0005` investigation audit JSONB (P5)

## Design references

See `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TOOLS.md`, `docs/INVESTIGATIONS.md`,
and the Cursor canvases.

## License

Private / learning project unless otherwise stated.
