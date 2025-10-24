# HalalWeee Catalog & Certification Slice

This module bootstraps the first service slice for HalalWeee: managing halal certifications and exposing a product catalog that only surfaces validly certified items.

## Getting Started

1. **Create a virtual environment** (Python 3.10+ recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Initialize (or refresh) the database** (SQLite file `halalweee.db` in project root):
   ```bash
   # Remove old file if upgrading schema
   rm -f halalweee.db
   python -m app.seed_data
   ```
   The script creates a sample IFANCA certification and a single poultry SKU. Running it again is idempotent.

3. **Start the API**:
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Explore**: visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive Swagger UI.

## Key Endpoints

- `POST /suppliers` — onboard a new supplier (contact info, status).
- `POST /suppliers/{id}/certifications` — link suppliers to approved halal certificates before listing SKUs.
- `POST /certifications` — create or ingest a certification document.
- `PATCH /certifications/{id}` — update status, expiry, or metadata.
- `POST /products` — register a SKU tied to both a supplier and a certification (validation blocks inactive or unlinked certs).
- `GET /products?certified_only=true` — fetch storefront-ready items with valid halal trust badges.
- `POST /warehouses` / `GET /warehouses` — manage fulfillment locations that hold inventory.
- `POST /products/{id}/inventory_lots` — add per-lot inventory with FEFO dates and temperature bands.
- `POST /products/{id}/prices` — attach pricing (regular, promo, subscription) with validity windows.
- `POST /orders` — create an order that automatically reserves inventory lots FEFO-style and prices against the configured ladder.
- `PATCH /orders/{id}` — cancel or fulfill an order, which releases/consumes reservations and keeps inventory accurate.
- `GET /events/outbox` — pull pending domain events (product, inventory, pricing, order) for downstream processing; `POST /events/outbox/{id}/ack` to mark them published/failed.
- `GET /products/{id}` — returns halal verification flag, aggregate inventory summary, and price ladder.

## Next Steps

- Expand reservations into two-phase commit with OMS/WMS, including partial fulfillment and substitution flows.
- Add promotion scheduling (campaign metadata, customer segments) and fiscal calendars.
- Replace polling endpoint with background dispatcher (Kafka/PubSub) and add dead-letter handling/retry strategies for the outbox.
- Emit domain events to Kafka/Pulsar instead of direct DB reads when broader system is in place.
- Wrap data changes with Alembic migrations once schema evolves past MVP.
