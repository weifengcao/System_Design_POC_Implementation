# Scribe System Design Talk Track (45 Minutes)

Time boxes assume a collaborative interview. Adjust pacing based on interviewer depth.

## 0. Setup (0-1 min)
- Confirm goals: recording workflows, sharing guides, enterprise-grade controls.
- Align on scale targets (MAU, guides/day), region requirements, AI expectations.

## 1. Requirements & Use Cases (1-5 min)
- Personas: Individual creator, team editor, enterprise admin.
- Functional highlights: capture, guide synthesis, editing, collaboration, sharing, integrations.
- Non-functional: latency, availability, compliance, data residency.
- Clarify exclusions (mobile, marketplace) to focus scope.

## 2. Capacity Planning (5-8 min)
- Present back-of-envelope numbers: sessions, storage growth, read vs write ratio, AI call volume.
- Call out implications: ingest throughput, media storage, cost considerations.

## 3. High-Level Architecture (8-18 min)
- Walk diagram: Agents → Ingestion → Streams → Guide Store → Collaboration → AI → Analytics.
- Emphasize multi-region layout (control plane vs data plane).
- Explain choice of Kafka + stream processing for ordering/scale; S3 + doc store for content.

## 4. Deep Dive: Recording & Processing Pipeline (18-28 min)
- Agent capture mechanics (buffering, encryption, PII guardrails).
- Gateway auth/rate limiting, fallback (SQS) for resilience.
- Stream processors: step boundary detection, screenshot dedupe, AI titling.
- Live previews: storing partial guide state, WebSocket updates.

## 5. Data & Collaboration Layer (28-35 min)
- Storage split: relational metadata vs document content vs object media.
- Versioning strategy, immutable history, CRDT/OT for co-editing.
- Search indexing (metadata + OCR) and caching layers.

## 6. Security & Compliance (35-40 min)
- Tenant isolation, RBAC, audit logging, DLP, encryption strategy, CMK option.
- Discuss data residency, hybrid deployment path, zero-trust edge.

## 7. Observability & Operations (40-43 min)
- Metrics, tracing, chaos testing, on-call workflow.
- DR/backup strategy, failover drills.

## 8. Trade-offs & Roadmap (43-45 min)
- Highlight major trade-offs (real-time vs cost, shared vs dedicated, AI outsourcing vs in-house).
- Future iterations: mobile capture, automation exports, marketplace.
- Leave room for advanced Q&A or explore an area interviewer cares about.
