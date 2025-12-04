SmartOCR
========

This is a minimal scaffolding for the SmartOCR MVP. It includes:
- API service (FastAPI) exposing sync and async OCR endpoints.
- In-memory job queue + stores orchestrated by a service layer (see `app/service.py`).
- OCR pipeline that ingests PDFs/images via Pillow/pdf2image and uses Tesseract when available; falls back to stub otherwise.
- Schema-driven field extraction lives in `app/extractors.py` using doc-type schemas defined in `app/schemas.py` (invoice/generic heuristics).

Project structure (core)
------------------------
- `app/main.py` – FastAPI entrypoint and routes.
- `app/models.py` – Pydantic request/response models.
- `app/pipeline.py` – OCR pipeline (PDF/image ingest + Tesseract/stub).
- `app/storage.py` – In-memory stores for documents/jobs.
- `app/queue.py` – Queue abstraction (in-memory; swap to SQS/Kafka/Redis).
- `app/queue_backends.py` – Queue backend adapters (in-memory; extendable).
- `app/repositories.py` – Job repository abstraction (in-memory; swap to Postgres).
- `app/service.py` – Service layer orchestrating jobs/pipeline/webhooks.
- `app/schemas.py` – Document type schemas (invoice, generic).
- `app/extractors.py` – Schema-driven field extraction/validators.
- `app/ingestion.py` – Upload validation (size/type guardrails).
- `app/db.py` – Postgres connection helper (env-driven).

Quick start
-----------
1) Install dependencies (Python 3.10+ recommended):
   ```
   pip install -r requirements.txt
   ```
2) Run the API:
   ```
   uvicorn app.main:app --reload
   ```
3) Try endpoints:
   - Health: `GET /health`
   - Sync OCR: `POST /ocr/extract` with a file upload (`file`) or JSON body `{ "source_url": "https://..." }`
   - Async OCR: `POST /ocr/jobs` with JSON `{ "source_url": "...", "external_id": "abc", "doc_type": "invoice" }` then `GET /ocr/jobs/{job_id}` or `GET /ocr/jobs`
   - Reviewer edit: `PATCH /ocr/jobs/{job_id}/fields` with `{ "fields": [...] }` to simulate human review.

Tests
-----
Run API tests with:
```
pytest -q
```

Notes
-----
- The pipeline is stubbed and does not perform real OCR yet. Replace `pipeline.py` with actual preprocessing/layout/recognition when models are wired.
- Storage and queue are in-memory; swap for S3/MinIO and SQS/Kafka/Redis as needed.
- OCR uses `pytesseract` if available; install Tesseract binary locally for real extraction, otherwise a stub response is returned. Data URIs (`data:image/png;base64,...`) are supported to avoid external fetches in tests.
- For PDF conversion install Poppler and set `POPPLER_PATH` if the binary is not on PATH. For Tesseract set `TESSERACT_CMD` if needed. Current field extraction is heuristic (invoice number, total, page_count, full_text); replace with structured schema and validators for production.
- Set `SMARTOCR_API_KEY` to enforce API key auth on all endpoints. Jobs support `webhook_url`; worker will POST the OCR result JSON on completion (best-effort, no retries yet). `WEBHOOK_TIMEOUT_SECONDS` controls webhook timeout.
- Webhooks now retry up to 3 times with a small backoff and emit logs. Basic numeric validation is applied to `total` extraction; extend with schema validators per document type.
- Service layer (`app/service.py`) abstracts job lifecycle; swap out `InMemory*` stores/queue with real DB/object storage/queue for production.
- `doc_type` is accepted on async jobs (and sync via query param) to allow schema-specific handling (e.g., invoice vs. generic); pipeline currently uses it to select heuristics.
- `app/ingestion.py` includes upload validation and an in-memory object store placeholder; replace with S3/MinIO and presigned URLs per PRD.
- Persistence: `app/repositories.py` and `app/queue_backends.py` provide interfaces to replace with Postgres and real queues; `app/db.py` reads `DATABASE_URL`.
- Tenant hinting: async jobs accept optional `tenant_id` for future multi-tenant isolation in storage/auth layers.
