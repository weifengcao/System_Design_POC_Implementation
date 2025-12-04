SmartOCR – System Design

1) Architecture Overview
- Entry: API Gateway handles auth (API keys/OIDC), rate limits, and validation for sync `/ocr/extract` and async `/ocr/jobs`.
- Ingestion: Presigned upload to object store (S3/MinIO). Metadata recorded in Postgres; job enqueued (SQS/Kafka).
- Orchestrator/Worker: Pulls jobs, runs pipeline stages with retries and trace correlation; writes artifacts/results back.
- ML Pipeline stages:
  1. Preprocess: deskew/denoise/resize/perspective fix; produce normalized page images.
  2. Layout detection: block/table/form detector (YOLO/Detectron). Outputs bounding boxes + types.
  3. Text recognition: OCR per block (TrOCR/Whisper-Vision) with CPU fallback (Tesseract).
  4. Field extraction: schema-aware mapping using prompted LLM + regex/heuristics; validators (totals check, MRZ checksum).
  5. Post-process: currency/date normalization, confidence aggregation, redaction if configured.
- Review Service/UI: Serves annotated images, applies edits, writes audit logs; exposes webhook/export.
- Monitoring: Prometheus/Grafana and OpenTelemetry tracing across API, worker, and pipeline stages.
- Deployment: Kubernetes; stateless API + workers; optional GPU nodes for detector/recognizer.

2) Module Responsibilities
- API Service (FastAPI/Go): Sync endpoint runs full pipeline inline (with timeout/size limits). Async endpoint enqueues jobs and exposes `/jobs/{id}` for status/results. Generates presigned upload URLs.
- Ingestion Worker: Validates uploads, converts PDFs to pages, stores originals/derivatives, enqueues per-document job.
- Pipeline Worker: Executes ML stages; uploads annotated artifacts; persists structured results (blocks, fields) and confidences; triggers webhooks on completion/error.
- Review Service: CRUD for review queues, edits, approvals; authorization checks; audit logging.
- Eval Service: Runs labeled batches to compute CER/F1; pushes metrics to monitoring; supports model version comparison.
- Admin: Key management, tenant settings (schemas, thresholds), feature flags for model versions.

3) Data Model (schema sketch, Postgres)
- tenants(id, name, region, settings_json)
- api_keys(id, tenant_id, key_hash, role, created_at, revoked_at)
- jobs(id, external_id, tenant_id, status, doc_type, page_count, source_uri, created_at, completed_at, error_code, webhook_url)
- pages(id, job_id, page_number, width, height, artifact_uri, text, confidence)
- blocks(id, page_id, bbox, type, text, confidence, reading_order)
- fields(id, job_id, name, value, bbox, confidence, validator_status, source_model, version)
- reviews(id, job_id, actor, action, before_json, after_json, created_at, reason)

4) API Surface (initial)
- POST `/ocr/extract` (sync): multipart upload or source URI; returns blocks + fields JSON; size ≤5MB; timeout ≤10s.
- POST `/ocr/jobs` (async): body {source_uri/external_id/doc_type/webhook_url}; returns job id.
- GET `/ocr/jobs/{id}`: status + result URLs + confidence summary.
- GET `/ocr/jobs/{id}/pages/{n}`: annotated image/PDF.
- PATCH `/ocr/jobs/{id}/fields`: reviewer edits; records audit.
- Admin endpoints: create/revoke API keys; set schemas and thresholds.

5) Pipeline Details
- Preprocess: OpenCV/Pillow; deskew by Hough lines; CLAHE for contrast; run in CPU container.
- Layout detection: YOLOv8n/v8s fine-tuned; batching for throughput; outputs bbox in normalized coords.
- Text recognition: TrOCR-base on GPU; auto-switch to Tesseract on CPU; language auto-detect limited to EN by default.
- Field extraction: LLM call with prompt containing schema and extracted text; regex/heuristics for totals, dates, MRZ; confidence = min(model + validator).
- Caching: Reuse layout/ocr for retries; memoize prompt responses per page hash where allowed.

6) Review UX (minimal)
- Queue view filtered by tenant/doc_type/status.
- Document view: page slider, overlay bboxes, inline field editing; confidence heatmap.
- Actions: approve/reject; download JSON/CSV; trigger re-run.

7) Observability & Reliability
- Metrics: request rate, p95 latency (API + per-stage), GPU util, queue depth, job failure rate, confidence distribution.
- Tracing: propagate `trace_id` from API through worker; spans per stage with artifact URIs.
- Alerts: SLA breach (latency/error), queue backlog, GPU unavailable, webhook failures.
- Resilience: retries with backoff on transient errors; circuit breaker around LLM and storage; poisoned-job quarantine.

8) Security & Compliance
- AuthZ: tenant-scoped API keys; RBAC (admin/reviewer/viewer) enforced at API/Review Service.
- Data: encryption in transit; storage encryption; presigned URLs short-lived; PII redaction in logs; configurable retention per tenant.
- Audit: all reviewer edits and admin actions logged with actor and timestamp.
- Isolation: per-tenant namespaces/buckets where needed; regional routing to satisfy residency.

9) Deployment Plan (MVP)
- Containers: api, worker, review, eval; shared Postgres, MinIO (or S3), Redis (cache), Kafka/SQS (queue).
- Environments: dev (CPU-only), staging (GPU optional), prod (GPU-backed node group).
- CI/CD: build/push images; run unit/integration tests; deploy via Helm/Kustomize; feature flags for model versions.

10) Build Roadmap (4-week alignment)
- Week 1: Stand up API + storage + queue; PDF/image ingestion; stub pipeline with Tesseract; Postgres schemas.
- Week 2: Integrate layout detector and TrOCR GPU path; sync/async end-to-end; result persistence; basic metrics.
- Week 3: Field extraction/validators for invoice/ID; review UI skeleton; webhook delivery.
- Week 4: Hardening (auth, rate limit, retries), eval harness on labeled set, dashboards, deployment manifests.
