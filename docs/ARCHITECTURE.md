# OpsMind — Architecture

This document points at the locked product/architecture decisions for the
**Self-Correcting Multi-Agent Operations Intelligence System**.

## Source of truth (Cursor canvases)

- **Architecture & plan:** `opsmind-final-architecture.canvas.tsx`
  (agents, layers, memory, grounding, security, stack, repo layout)
- **Implementation roadmap:** `opsmind-implementation-roadmap.canvas.tsx`
  (P0–P8 build order, tests, exit criteria)

Canvases live under the Cursor project `canvases/` directory (IDE-managed),
not necessarily inside this git repo.

## Locked MVP summary

| Item | Decision |
|------|----------|
| Agents | 6 — Planner, Data Investigator, Knowledge, Synthesizer, Critic, Recommender |
| Orchestration | LangGraph with max 2 critique retries |
| Stack | Python, FastAPI, Postgres + pgvector, Docker Compose |
| Data | Synthetic ecommerce/warehouse DB + playbook RAG |
| Memory | Working checkpoints, episodic runs, org RAG, case memory on approve |
| Grounding | Cite-or-abstain + citation verifier |
| Actions | Human approve/reject stub only (no real side effects) |

## Repository map (P0)

| Path | Responsibility |
|------|----------------|
| `apps/api/` | FastAPI service (`/health`, `/ready`, future investigation APIs) |
| `apps/web/` | Operator console (P6) |
| `packages/opsmind/` | Shared domain, db, graph, agents, tools, guardrails, memory, grounding |
| `data/playbooks/` | SOP / playbook markdown sources |
| `evals/` | Golden cases + runner (P7) |
| `docs/` | Architecture notes, seed scenarios, demo script |
| `docker-compose.yml` | API + Postgres (pgvector) |

## Phase status

- **P0 Foundation** — Compose, health/ready, config, Alembic baseline
- **P1 Business data plane** — schema, deterministic seed, planted scenarios (`docs/SEED_SCENARIOS.md`), read-only role
- **P2 Tools + evidence persistence** — allowlisted SQL, date normalizer, playbook RAG, memory tables (`docs/TOOLS.md`)
- **P3 LangGraph agent skeleton** — 6 agents, checkpoints, `POST/GET /investigations` (`docs/INVESTIGATIONS.md`)
- **P4 Self-correction + grounding** — Critic retries, citation verifier, abstain statuses (`docs/SELF_CORRECTION.md`)
- **P5 Security, guardrails, auth** — API key auth, input/output guardrails, RAG sanitize, tool budgets, audit (`docs/SECURITY.md`)
- **P6 Operator UI + Case Memory** — React/Vite/Tailwind operator console, live DAG, timeline, evidence citations explorer, approve/reject reviews, episodic case memory (`apps/web`)
- **P7 Evaluation harness** — 12 golden benchmark cases, multi-metric scoring engine, CLI runner & markdown scorecard generator (`docs/EVAL_BASELINE.md`)
- **P8 Demo walkthrough & runbook** — End-to-end incident walkthroughs, failure modes, abstention, guardrails & evaluation guide (`docs/DEMO_SCRIPT.md`)
