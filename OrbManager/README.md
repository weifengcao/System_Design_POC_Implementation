# OrbManager Proof of Concept

This directory contains a small FastAPI-based control plane that demonstrates key flows for managing distributed smart hardware ("orbs"). It pairs with the architecture described in `design.md` and focuses on:
- Tenant + orb registration
- Telemetry ingestion with basic rule evaluation (low battery alerts)
- Command dispatch with acknowledgement + expiration worker
- Alert retrieval & fleet visibility APIs
- In-memory storage (state resets when the process restarts)

## Getting Started
1. **Create a virtual environment & install deps**
   ```bash
   cd OrbManager
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the API**
   ```bash
   uvicorn app.main:app --reload
   ```
   Interactive docs will be available at `http://localhost:8000/docs`.

## Example Workflow
1. Create a tenant:
   ```bash
   curl -X POST http://localhost:8000/tenants \
     -H 'Content-Type: application/json' \
     -d '{"name": "RoboRide", "contact_email": "ops@roboride.example"}'
   ```
2. Register an orb (replace `TENANT_ID` with the UUID returned above):
   ```bash
   curl -X POST http://localhost:8000/orbs/register \
     -H 'Content-Type: application/json' \
     -d '{"tenant_id": "TENANT_ID", "name": "orb-007", "orb_type": "robotaxi", "firmware_version": "1.0.0"}'
   ```
3. Push telemetry (low battery triggers an alert):
   ```bash
   curl -X POST http://localhost:8000/telemetry \
     -H 'Content-Type: application/json' \
     -d '{"orb_id": "ORB_ID", "battery_pct": 18, "latitude": 37.78, "longitude": -122.4, "speed": 6.2}'
   ```
4. Issue a command:
   ```bash
   curl -X POST http://localhost:8000/commands \
     -H 'Content-Type: application/json' \
     -d '{"orb_id": "ORB_ID", "command_type": "return_to_base", "payload": {"target_station": "SF-01"}}'
   ```
5. Simulate the orb fetching pending commands:
   ```bash
   curl http://localhost:8000/commands/pending/ORB_ID
   ```
6. Acknowledge the command:
   ```bash
   curl -X POST http://localhost:8000/commands/COMMAND_ID/ack \
     -H 'Content-Type: application/json' \
     -d '{"status": "acknowledged", "payload": {"received_at": "2024-06-04T10:00:00Z"}}'
   ```
7. Inspect alerts:
   ```bash
   curl http://localhost:8000/alerts?orb_id=ORB_ID
   ```

The background worker automatically expires pending/dispatched commands when their TTL elapses.
