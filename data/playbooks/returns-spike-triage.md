# Returns Spike Triage SOP

## Trigger
Return count or refund total rises materially week-over-week for a SKU or reason code.

## Triage steps
1. Group returns by reason and SKU for the incident window.
2. Watch for quality codes such as `defective_seal` (example: Smart Water Bottle / `SKU-1002`).
3. Quarantine remaining on-hand inventory if defect rate is elevated.
4. Open supplier quality ticket with return sample photos / lot data.
5. Update PDP copy / CX macros while root cause is open.

## Decision thresholds
- Reason concentration >40% on one code → quality hold.
- Multi-SKU spike → check carrier damage and packaging changes.

## Evidence
Returns-by-reason SQL output, refund totals, and linked order dates.
