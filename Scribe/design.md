# Scribe-Scale Workflow Capture Platform Design

## 1. Problem Statement
Design a planet-scale SaaS platform, inspired by [scribe.com](https://scribe.com/), that automatically captures user workflows (screen, clicks, text) and converts them into shareable step-by-step guides enriched with screenshots, annotations, and automation metadata. The platform must support:
- Native desktop and browser extensions that record workflows in near real time.
- Secure storage, editing, collaboration, and sharing of generated guides.
- AI-powered redaction, annotation suggestions, and automation recommendations.
- Enterprise-grade governance, RBAC, audit, and data residency guarantees.

Target scale: >10M monthly active users (MAU), thousands of concurrently recording sessions per minute, supporting both SMB and large enterprise tenants.

## 2. Requirements and Assumptions

### Functional
- **Recording Agents**: Browser extension + desktop client capture UI events (DOM interactions, keystrokes, screenshots, screen video snippets) with minimal performance impact.
- **Guide Synthesis**: Server-side service converts streams of events into structured steps with titles, descriptions, visuals, and metadata (app context, URLs).
- **Editing Experience**: Web editor enabling users to refine steps, redact sensitive data, reorder, add annotations, embed video/gif.
- **Collaboration**: Workspace model with shared folders, comments, version history, real-time co-editing.
- **Sharing**: Public/Private links, embeddable widgets, exports (PDF, HTML, Markdown), integration with knowledge bases (Confluence, Notion).
- **AI Assistance**: LLM-driven summarization, step titling, screenshot callouts, automated redaction suggestions, voice-over generation.
- **Search & Discovery**: Full-text search across steps, tags, metadata; tenant-level analytics on usage.
- **Integrations**: Webhooks, APIs for automations (e.g., trigger RPA, connect to help desks).

### Non-Functional
- 99.95% availability for guide access APIs; <150 ms P95 guide read latency for cached content.
- Recording upload round-trip <1s for perceived real-time feedback.
- Data durability 11 9s, encryption at rest/in transit, tenant isolation.
- Regional data residency options (US, EU, APAC) with compliance (SOC2, GDPR, HIPAA optional add-on).
- Support hybrid cloud deployment for regulated customers.
- Observability: per-tenant usage metrics, SLA monitoring.

### Out of Scope (initial version)
- Native mobile capture.
- Branching workflows / decision trees (not core focus).
- Marketplace for templates (future milestone).

### Assumptions
- Modern cloud environment (AWS reference).
- Multi-tenant SaaS; ability to spin dedicated clusters for large enterprise if needed.
- Agent binaries auto-update via secure channel.

## 3. Capacity Estimation (Year 2 conservative)
- 10M MAU, 2M DAU.
- Peak concurrent recording sessions: 50K.
- Avg workflow session: 40 steps, ~150 events, 40 screenshots (50 KB each) → ~2 MB raw images per session.
- Daily new guides: 3M (including drafts). Storage growth:
  - Screenshots/images: ~6 PB/year (with dedupe + compression to 25% reduces to 1.5 PB/year).
  - Metadata + text: 3 KB/step → ~120 KB per guide → 0.35 PB/year.
- Read traffic: 10x writes (viewing guides multiple times) → peak 300K QPS for guide fetch (cacheable).
- AI inference: avg 2 LLM calls per guide creation (e.g., summarization, redaction suggestions) → 6M LLM requests/day.

## 4. Core Architecture Overview
```
┌──────────────┐        ┌─────────────────────┐         ┌─────────────────────┐
│ Recording    │  gRPC  │ Ingestion Gateway   │  Kafka  │ Event Processing     │
│ Agents       ├───────►│ (mTLS, authz, WAF)  ├────────►│ (Stream processors) │
└──────────────┘        └─────────────────────┘         └────────┬────────────┘
                                                                      │
                                                          ┌───────────┴─────────┐
                                                          │                     │
                                                  Structured Metadata      Media Pipeline
                                                (Guide Composer Service)   (Screenshot svc)
                                                          │                     │
                                              ┌───────────┴──────────┐          │
                                              │  Guide Store          │          │
                                              │  (Aurora + DocStore)  │          │
                                              └───────────┬──────────┘          │
                                                          │                     │
                                             ┌────────────┴────────────┐       │
                                             │ Collaboration & Sharing │◄──────┘
                                             │    (API, Web, Search)   │
                                             └────────────┬────────────┘
                                                          │
                                       ┌──────────────────┴──────────────────┐
                                       │ AI Services (redaction, summarizer) │
                                       └──────────────────┬──────────────────┘
                                                          │
                                                Analytics & Telemetry Lake
```

### Component Breakdown
- **Recording Agents**: Capture DOM mutations, keyboard shortcuts, screen segments; locally buffer, compress, encrypt, and stream via WebSocket/gRPC. Perform client-side PII detection to avoid capturing sensitive fields.
- **Ingestion Gateway**: Global Anycast endpoints (CloudFront + API Gateway/Envoy). Performs API key validation, OAuth device tokens, rate limiting, payload normalization. Writes events to Kafka (multi-region) and fallback to SQS when Kafka unavailable.
- **Event Processing / Guide Composer**:
  - Stream processors (Flink or Kafka Streams) assemble raw events into ordered steps, detect step boundaries (heuristics + ML), trigger screenshot cropping, and call AI services for step titles.
  - Materialize intermediate state into Redis/Scylla for low-latency preview updates.
  - On finalize, persist to **Guide Store** (metadata to Aurora Postgres for transactional operations; step content & layout to Document DB like DynamoDB/DocumentDB).
- **Media Pipeline**: Handles screenshot ingestion, dedupe via perceptual hashing, stores in S3 w/ Glacier tiering, generates derivatives (thumbnail, blurred, annotated). CDN (CloudFront) for delivery with signed URLs.
- **Collaboration & Sharing API**: GraphQL/REST servicing web app; uses Elasticache for session data, DocumentDB for guides, Aurora for RBAC/team data. Real-time edits via WebSockets (AWS AppSync or custom SignalR service).
- **Search Service**: Ingests guide metadata into OpenSearch; screenshot OCR pipeline (Textract) feeds text for full-text search.
- **AI Platform**: Abstraction layer over internal models + third-party LLMs. Handles prompt templates, rate limiting, caching, redaction suggestions, voice-over generation. Requires data governance + PII scrubbing before sending to third parties.
- **Analytics Lake**: Raw events, usage metrics stored in S3-based lake (Parquet) with Glue catalog; pipelines to Snowflake/Redshift for BI dashboards per tenant.

## 5. Data Model Sketches

### Relational (Aurora Postgres)
- `tenants(id, name, plan, region, settings, created_at)`
- `users(id, tenant_id, email, role, status, last_login_at)`
- `guides(id, tenant_id, owner_id, status, created_at, last_modified_at, published_at, version)`
- `guide_collaborators(guide_id, user_id, permissions)`
- `folders(id, tenant_id, parent_folder_id, name)`
- `guide_folder_membership(guide_id, folder_id)`
- `audit_logs(id, tenant_id, actor_id, action, resource_type, resource_id, metadata, created_at)`

### Document Store (DynamoDB)
- `GuideContent` table keyed by `guide_id`, range key `version`. Contains JSON: steps array (id, order, description, DOM selector, annotations), layout metadata, AI suggestions.
- `LiveSessions` table for ongoing recordings (keyed by session_id) storing latest step preview state.

### Object Storage
- `s3://scribesite-media/{tenant_id}/{guide_id}/{version}/screenshot_{step_id}.png`
- `s3://.../redacted/{...}` for derivative assets.

### Search Index (OpenSearch)
- Document per guide version: fields include tenant_id, title, tags, step_text (flattened), OCR text, integration metadata.

## 6. Tenant Isolation & Multi-Region Strategy
- **Control Plane**: Multi-region active-active cluster managing tenant metadata and routing. Uses Route 53 latency-based routing with health checks.
- **Data Plane**: Region-specific clusters containing Guide Store, Search, Media. Tenants assigned based on region selection; cross-region read replicas for DR.
- **Dedicated Tenants**: Option for VPC isolation; deploy separate stack with AWS Control Tower/landing zone.
- **Edge Caching**: CDN caches published guides, while private guides require signed URLs and token validation.

## 7. Workflow Lifecycle
1. **Start Recording**: Agent authenticates using OAuth device flow (tenant delegated tokens). Receives session_id, encryption keys (enveloped with device key).
2. **Event Capture**: Agent intercepts UI actions, groups events per step using heuristics (time thresholds, DOM hierarchy). Each step includes screenshot capture and optional video snippet.
3. **Upload**: Agent uploads event batches (gRPC streaming) to ingestion gateway; if offline, stores locally and retries with exponential backoff.
4. **Stream Processing**: Kafka Streams consumer aggregates events, runs classification ML (determine step title, highlight areas). When step boundary detected, writes preview to LiveSessions table; notifies Web client via WebSocket.
5. **Guide Finalization**: On user stop, agent sends finalize request. Guide Composer writes data to GuideContent, updates relational metadata, triggers AI summarizer to create description, runs redaction suggestions.
6. **Editing & Collaboration**: Web editor fetches guide content, allows modifications. Real-time engine uses operational transforms/CRDT (Automerge) to sync edits. Save operations create new versions (immutable).
7. **Publishing & Sharing**: When published, CDN invalidation triggered. Permissions enforced via pre-signed access tokens; audit log entry recorded.
8. **Analytics**: Usage events (views, shares) stream to analytics lake; aggregated dashboards per tenant.

## 8. Scaling and Performance Considerations
- **Ingestion**: Kafka clusters sized for peak throughput (~1M events/sec). Use partitioning by tenant_id + session_id to ensure ordering and parallelism.
- **Guide Computation**: Stateless microservices autoscale using K8s; backpressure via Kafka consumer lag. For heavy ML steps, use separate async job queue (SQS + AWS Batch) to avoid delaying core processing.
- **Storage**: DynamoDB uses on-demand capacity with adaptive capacity per partition. S3 lifecycle policies move old media to cheaper tiers.
- **Caching**: Guide metadata cached in Redis; CDN for static assets. For private guides, use signed cookies with short TTL and background refresh.
- **Redaction**: Early detection at agent + server ensures sensitive data not persisted. Provide tenant-managed redaction policies.

## 9. Security, Privacy, and Compliance
- End-to-end encryption: Agents encrypt payloads with per-session keys; server stores keys in KMS. Option for customer-managed keys (CMK).
- Device attestation (code signing, notarization) to prevent tampering. Use secure auto-update with signed packages.
- RBAC: Roles (Viewer, Editor, Admin) plus custom per-tenant policies. Attribute-based access control for sensitive guides.
- Audit logging: immutable append-only log (AWS QLDB or Kafka + S3) accessible to tenant admins.
- DLP: On ingest, run OCR + text classification filters; block uploads violating policy.
- SOC2 Type II, GDPR compliance, data processing agreements. Support right-to-be-forgotten by scrubbing user PII across stores.

## 10. Observability and Operations
- Metrics: Ingestion QPS, Kafka lag, guide creation latency, AI success rate. Dashboard via Prometheus + Grafana.
- Distributed tracing (OpenTelemetry) connecting agent -> gateway -> backend services.
- Alerts: SLA breaches, storage consumption thresholds, AI provider failures.
- Chaos testing: Simulate Kafka outages, KMS failures, partial region outages.
- Incident response runbooks, on-call rotation; SLO budgets for availability and latency.

## 11. Extensibility & Roadmap
- **Future features**: Mobile capture, workflow branching, automation export (e.g., Selenium/Puppeteer scripts), knowledge base recommendations, templating marketplace.
- **ML Enhancements**: Personalized step descriptions, automated video voice-overs in multiple languages, context-aware guides (adapt to user environment).
- **Enterprise**: SCIM provisioning, SIEM integrations, eDiscovery exports.
- **Hybrid Deployments**: On-prem connector for regulated customers; use Kubernetes distribution (EKS Anywhere) + Terraform modules.

## 12. 45-Minute Interview Flow (Staff+)
1. Clarify scope & personas (3 min).
2. Capacity planning & workload estimation (5 min).
3. High-level architecture (10 min).
4. Deep dive on ingestion pipeline & guide synthesis (10 min).
5. Discuss data storage/collaboration & security/compliance (10 min).
6. Address observability, resilience, roadmap (5 min).
7. Summarize trade-offs & questions (2 min).

### Key Trade-offs to Highlight
- Fan-out vs real-time preview consistency: use eventual consistency for collaborator previews; per-step confirmation for author.
- Cost vs quality for AI inference: use caching + distillation to lower inference spend; fallback to heuristic redaction when LLM quota exceeded.
- Multi-tenant vs single-tenant stacks: default shared control plane, escalate to dedicated clusters for large enterprises.

---

This design balances rapid guide creation, collaboration, and AI augmentation with enterprise-grade security and scalability requirements expected of a Scribe-like platform.
