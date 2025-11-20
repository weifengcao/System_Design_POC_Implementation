# AITrust – LLM Trust Layer

AITrust is a lightweight gateway that enforces guardrails for LLM interactions. It exposes a FastAPI service that performs synchronous checks, logs every request to Postgres, and fans out heavy scanning jobs to Celery workers. Redis is used both as a task queue and as a cache for repeated verdicts.

## Features
- **API Gateway** (`/check`) with API key authentication.
- **Guardrails** via `PolicyEngine` (keywords, prompt-injection markers, basic PII heuristics).
- **Caching** of verdicts to reduce repeated work.
- **Audit Logging** to PostgreSQL for compliance and observability.
- **Async Scans** using Celery workers (placeholder implementation to plug in ML models).

## Getting Started
1. Copy secrets (dev defaults provided):
   ```bash
   cp secrets/postgres_password.example secrets/postgres_password.txt
   cp secrets/redis_password.example secrets/redis_password.txt
   cp secrets/aitrust_api_key.example secrets/aitrust_api_key.txt
   ```
2. Run the stack:
   ```bash
   docker compose up --build
   ```
3. Hit the API:
   ```bash
   curl -X POST http://localhost:8001/check \
     -H "Content-Type: application/json" \
     -H "X-API-Key: $(cat secrets/aitrust_api_key.txt)" \
     -d '{"text": "Can I share my password?"}'
   ```

### Running Locally
Use Poetry (or plain pip) to install dependencies:
```bash
cd AITrust
poetry install
poetry run uvicorn AITrust.api.main:app --reload
```

### Tests
```bash
cd AITrust
pytest
```

## Project Layout
```
AITrust/
├── api/                # FastAPI application
├── core/               # Config, policy engine, cache, Celery wiring
├── tests/              # Pytest suite
├── docker-compose.yml  # Dev stack with Postgres + Redis
└── design_doc.md       # High-level system design
```

## Next Steps
- Replace the placeholder Celery scan task with actual ML model invocations.
- Extend policy checks (toxicity scoring, per-tenant allow/block lists).
- Emit structured metrics/logs for downstream monitoring systems.
