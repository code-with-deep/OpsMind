# Carrier Delay Response Guide

## Trigger
Elevated late deliveries (`delivered_late`) or rising average delay hours for a carrier.

## Diagnosis steps
1. Run carrier SLA query for the incident window vs prior week.
2. Isolate the offending carrier (example: **FastShip Express**).
3. Measure customer-impacted regions and order volume on that carrier.
4. Check whether SLA breaches coincide with promo volume spikes.

## Response options
- Shift new shipments to backup carriers for 48–72 hours.
- Notify CX with delay macro and revised promise dates.
- Open carrier QBRs with delay evidence attached.

## Exit criteria
Late rate returns within SLA band for 3 consecutive days and backlog clears.
