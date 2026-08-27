# OpsMind

**Self-Correcting Multi-Agent Operations Intelligence System** for ecommerce / warehouse operations.

OpsMind investigates operational questions, gathers evidence from business data and playbooks, critiques its own conclusions, self-corrects when evidence is weak, and returns an evidence-backed recommendation for a human operator.

> Not a chatbot. Claims must be grounded in tool evidence (cite-or-abstain).

## Current status

**Phase 0 — Foundation** complete: FastAPI + Postgres (pgvector) via Docker Compose, `/health` + `/ready`, config, Alembic baseline.

## Quick start (P0)

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2+)
- Git

### 1. Environment file

```powershell
cd "d:\PROJECTS\AI Projects\OpsMind"
Copy-Item .env.example .env
```

### 2. Start the stack

```powershell
docker compose up --build -d
```

### 3. Smoke checks

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

- `/health` → `200` with `"status":"ok"` (process alive)
- `/ready` → `200` with `"status":"ready"` and database `ok` (DB reachable)

API docs: http://localhost:8000/docs

### 4. Stop

```powershell
docker compose down
```

## Layout

```text
apps/api/           FastAPI application
apps/web/           Operator UI (Phase 6)
packages/opsmind/   Shared packages (db, agents, graph, tools, ...)
data/playbooks/     SOP markdown (Phase 2 RAG)
evals/              Golden evals (Phase 7)
docs/               Architecture and runbooks
docker-compose.yml  api + db
alembic.ini         Migration config
```

## Migrations (Alembic)

With the DB up and dependencies installed locally (optional):

```powershell
$env:DATABASE_URL_SYNC = "postgresql://opsmind:opsmind@localhost:5432/opsmind"
alembic upgrade head
```

P0 baseline is empty; business tables arrive in Phase 1.

## Design references

See `docs/ARCHITECTURE.md` and the Cursor canvases:

- Final architecture canvas
- Implementation roadmap canvas (P0–P8)

## License

Private / learning project unless otherwise stated.
