# OpsMind Phase 3 — Investigation graph

LangGraph happy path with 6 agents. Critic is pass-through in P3
(self-correction loop arrives in P4).

## Flow

```text
Planner → Data Investigator ⎤
          Knowledge          ⎦ → Synthesizer → Critic → Recommender
```

## API

```powershell
# Run a full investigation (waits for completion)
Invoke-RestMethod -Method POST http://localhost:8000/investigations `
  -ContentType application/json `
  -Body '{"question":"Why did our revenue decrease this week (2026-08-17 to 2026-08-23), and what should we do?"}'

# Reload from DB
Invoke-RestMethod http://localhost:8000/investigations/<id>
```

Response includes `status`, `timeline`, `findings`, `plan`, `hypothesis`,
`critique`, and `recommendation`.

## Models

- Fast (`LLM_MODEL_FAST`): Planner (when `LLM_API_KEY` is set)
- Strong (`LLM_MODEL_STRONG`): Synthesizer + Recommender

If `LLM_API_KEY` is empty, agents use a **deterministic heuristic path** that
still runs real SQL + RAG tools — useful for local demos and tests.

## Checkpoints

Graph state is checkpointed with `langgraph-checkpoint-postgres` when available
(`thread_id` = investigation UUID). Episodic evidence remains in
`investigations` / `investigation_events` / `findings` / `tool_invocations`.
