# ExpiredCoupons POC

This proof of concept demonstrates the core expiration pipeline described in `design.md`. It loads sample coupons, identifies those expiring within a configurable time window, simulates deactivation fan-out across redemption channels, and issues notifications.

## Project Layout
- `data/sample_coupons.json` – fixture with representative coupon metadata.
- `src/models.py` – lightweight data classes representing coupons and processing results.
- `src/storage.py` – in-memory repository that supports range queries for upcoming expirations.
- `src/ingestion.py` – loader that converts JSON payloads into domain objects.
- `src/services/*` – simulated deactivation and notification adapters.
- `src/orchestrator.py` – orchestrates expiration workflow, state transitions, and reporting.
- `poc.py` – executable runner that ties components together.

## Running the POC

```bash
cd ExpiredCoupons
python poc.py --verbose
```

Arguments:
- `--data-file` – alternate coupon dataset (defaults to bundled fixture).
- `--window-seconds` – lookahead window for expiring coupons (default 2 hours).
- `--current-time` – seed time used to evaluate expiration (ISO-8601).
- `--verbose` – enable debug logging for deeper visibility.

The script prints per-coupon transitions and a rollup summary. Channel adapters and notifications are simulated with logging, but the architecture mirrors production concepts (repository, orchestrator, fan-out, observability).
