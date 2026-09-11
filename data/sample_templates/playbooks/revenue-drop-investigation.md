# Revenue Drop Investigation Playbook

## Purpose
Use this playbook when operators ask why revenue decreased versus a prior period.

## Required comparisons
1. Compare **problem week** revenue totals to **prior week**.
2. Break down revenue by SKU mix.
3. Check cancellations and refunds in the same window.
4. Cross-check inventory stockouts, carrier SLA, campaigns, and returns.

## Investigation checklist
- Pull `revenue_week_totals` for both windows.
- Pull `sku_revenue_mix` and note share shifts.
- Inspect cancelled orders and top lost SKUs.
- Confirm at least two independent drivers before recommending action.

## Escalation
If revenue drop exceeds 20% week-over-week, open a P1 ops war-room and attach SQL evidence before proposing promotions or carrier changes.
