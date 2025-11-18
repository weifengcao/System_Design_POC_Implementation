# LastMile Proof Of Concept

This directory contains the design document plus a lightweight simulation that demonstrates how agent-driven orchestration can schedule orders onto different vehicle types while reacting to live hazards.

## Files
- `design.md` – system goals, agents, and architecture.
- `poc.py` – runnable script that stitches simplified agents together (order intake, capacity, signals, planner, router, SLA guard).

## Running The POC
```bash
python LastMile/poc.py [--orders-file orders.json] [--drivers-file drivers.json] [--skip-updates] [--hazard-seed 123]
```

Default behavior:
1. Load built-in fixture orders/drivers.
2. Produce an initial plan.
3. Simulate a priority upgrade and a new rush order, then re-run planning to showcase re-optimization under capacity/weight constraints.

The CLI flags let you inject your own data:
- `--orders-file`: JSON array matching the fixture structure (`pickup_label`, `pickup_coord`, `dropoff_label`, `dropoff_coord`, `promise_minutes`, optional `priority`, `handling`, `weight_kg`).
- `--drivers-file`: JSON array with driver definitions (`id`, `mode`, `speed_kmph`, `capacity`, `max_payload_kg`, `shift_hours`, and a nested `location` block `{ "label": "...", "coord": [x, y] }`).
- `--skip-updates`: Run only the initial plan.
- `--hazard-seed`: Control random hazard multipliers for reproducible scenarios.

Each run prints:
1. Hazard map per zone.
2. Driver assignments with priority tiers and payload feasibility.
3. Routes with ETAs and promise windows.
4. SLA Guardian report highlighting early/late deliveries.

Use these outputs to reason about planner heuristics before hardening into services described in `design.md`.
