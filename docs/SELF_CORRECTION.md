# OpsMind Phase 4 — Self-correction + grounding

Critic can force retries; citation verifier blocks ungrounded claims; Planner
can abstain with `unsupported` / `needs_clarification`.

## Statuses

| Status | Meaning |
|--------|---------|
| `completed` | Grounded recommendation shipped |
| `unsupported` | Outside ecommerce/warehouse catalog |
| `needs_clarification` | Too vague to investigate |
| `insufficient_evidence` | Retries exhausted or citations failed |
| `needs_retry` | Transient Critic state mid-loop |

## Graph (P4)

```text
Planner ─(unsupported/clarify)─► END
   │
   └─► Data ∥ Knowledge → Synthesizer → Critic
                                      │
                          pass ───────┼─► Recommender (+ citation verifier) → END
                          retry ──────┼─► Planner (gap-aware replan)
                          fail_soft ──┴─► insufficient_evidence → END
```

## Manual checks

```powershell
# Happy path
Invoke-RestMethod -Method POST http://localhost:8000/investigations `
  -ContentType application/json `
  -Body '{"question":"Why did our revenue decrease this week (2026-08-17 to 2026-08-23), and what should we do?"}'

# Unsupported
Invoke-RestMethod -Method POST http://localhost:8000/investigations `
  -ContentType application/json `
  -Body '{"question":"write a poem about warehouses"}'

# Needs clarification
Invoke-RestMethod -Method POST http://localhost:8000/investigations `
  -ContentType application/json `
  -Body '{"question":"why are things bad?"}'
```
