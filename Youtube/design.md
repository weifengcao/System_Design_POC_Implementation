# YouTube MVP System Design

## 1. Overview
Design a minimum viable product (MVP) for a YouTube-like video sharing platform that can support global distribution, high-volume uploads, and personalized discovery while meeting a Staff+ level bar for scalability, reliability, and operational excellence.

## 2. Goals and Requirements

### 2.1 Functional Requirements
- Users create accounts, manage channels, upload videos with metadata (title, description, tags, thumbnail).
- Platform transcodes uploads into adaptive bitrate formats and publishes them once processing completes.
- Viewers browse home feed, search for videos, watch playback with adaptive streaming, and interact (like, comment, subscribe).
- Creators view basic analytics (views, watch time, engagement).
- Moderation pipeline flags or removes policy-violating content.

### 2.2 Non-Functional Requirements
- Availability (API / playback): 99.9% monthly SLA.
- Latency: initial playback startup < 2 seconds p95; metadata reads < 150 ms p95.
- Durability: zero data loss for uploaded videos and metadata.
- Scalability target: 10M MAU, 200k peak concurrent viewers, 50k uploads per day.
- Observability: full tracing across ingest and playback; alertable metrics and dashboards.

### 2.3 Out of Scope (MVP)
- Live streaming.
- Ads/monetization stack.
- Long-tail advanced analytics (heatmaps, cohort reports).
- Enterprise DRM requirements.

## 3. Key Assumptions
- Content stored in replicated object storage (e.g., Amazon S3) with lifecycle management for cost control.
- CDN provider handles global edge caching; origin located in two primary regions (multi-active).
- Transcoding performed in a single region with warm standby.
- OAuth2 compatible identity provider handles authentication; authorization managed in-house.
- Network bandwidth cost optimized by heavy reliance on CDN (>90% hit rate).

## 4. High-Level Architecture
1. **Edge Layer**: Anycast DNS → CDN (CloudFront/Akamai) for video segments, thumbnails, static assets.
2. **API Layer**: API Gateway / Global Load Balancer → Authentication Service → microservices in Kubernetes.
3. **Core Services**: Upload Service, Metadata Service, Transcoding Orchestrator, Playback Service, Search Service, Recommendation Service, Notification Fanout.
4. **Data Platform**: Kafka event bus, stream processors (Flink/Spark Structured Streaming), batch analytics (Spark on EMR), feature store, data lake (S3 + Glue catalog).
5. **Storage**: Object storage buckets for raw uploads and processed renditions; Relational DB (PostgreSQL with Citus) for metadata; Elasticsearch for search index; Redis for hot caches.

## 5. Core Components

### 5.1 API Gateway & Authentication
- Provides rate limiting, request validation, JWT issuance/verification.
- Fanout to regional clusters using service discovery (e.g., Envoy + xDS).

### 5.2 Upload Service
- Issues pre-signed URLs for chunked, resumable uploads (Tus protocol or S3 multipart).
- On completion, writes video metadata (idempotent `video_id` ULID) to Metadata Service and publishes `VideoUploaded` event to Kafka.
- Stores raw asset in `s3://youtube-raw/{upload_date}/{video_id}/{chunk}` with MD5 for integrity.

### 5.3 Transcoding Pipeline
- Orchestrator consumes `VideoUploaded` events, enqueues transcoding jobs to SQS/Kinesis.
- Workers (EC2/GPU nodes) fetch raw video, use FFmpeg to generate multi-bitrate HLS/DASH renditions (e.g., 1080p @ 6 Mbps, 720p @ 3 Mbps, 480p @ 1.5 Mbps, 360p @ 800 kbps) and separate audio tracks.
- Output written to `s3://youtube-vod/{video_id}/{representation}`; manifest (M3U8/MPD) generated and persisted.
- Status updates persisted in Metadata Service (`processing_state`) and failure retries handled with exponential backoff and DLQ.

### 5.4 Metadata Service
- PostgreSQL (Citus) for sharded tables: `videos`, `channels`, `playlists`, `user_profiles`, `engagement_metrics`.
- Change Data Capture (Debezium) streams updates to Kafka; consumers update Search index and Recommendation features.
- Exposes gRPC/REST for video CRUD, state transitions, and data retrieval.

### 5.5 Playback Service
- Validates video availability (state `READY`, user entitlement, region restrictions).
- Returns signed manifest URL and playback metadata (title, duration, captions).
- Coordinates with CDN by pre-warming manifests on publish and invalidating on re-encode.

### 5.6 Search Service
- Elasticsearch/OpenSearch cluster with analyzers for language-specific tokenization.
- Index pipelines ingest metadata and engagement signals (views, likes) for ranking.
- Query layer provides type-ahead, filters, and pagination; caches popular queries in Redis.

### 5.7 Recommendation Service
- Offline: batch jobs compute collaborative filtering co-watch graph and trending score per locale.
- Nearline: streaming jobs update per-user embeddings and session signals stored in feature store.
- Online inference service blends candidate sets (watch history, similar creators, trending) and ranks using lightweight gradient boosted trees model.
- Results cached per user for minutes; freshness ensured by invalidating on new significant events (upload, subscription, watch completion).

### 5.8 Notification & Subscription Service
- Kafka topics for events (`VideoReady`, `NewComment`, `SubscriptionCreated`).
- Fanout workers update notification preferences (email/mobile) and push to WebSocket/FCM as needed.

### 5.9 Moderation & Compliance
- Ingest pipeline performs hash matching (PhotoDNA), ML models (NSFW, violence) and flags to human review queues.
- Manual reviewer tool backed by Metadata Service with audit logging.

## 6. Data Model Highlights

```sql
-- videos table (sharded by video_id)
video_id        UUID      PK
channel_id      UUID      FK channels.channel_id
title           TEXT
description     TEXT
tags            TEXT[]
status          ENUM('UPLOADED','PROCESSING','READY','BLOCKED','DELETED')
visibility      ENUM('PUBLIC','UNLISTED','PRIVATE')
duration_sec    INT
manifest_url    TEXT
thumbnails      JSONB     -- variant URLs
created_at      TIMESTAMP
updated_at      TIMESTAMP

-- engagements (time-series fact table partitioned by day)
video_id        UUID
date            DATE
views           BIGINT
watch_time_sec  BIGINT
likes           BIGINT
dislikes        BIGINT
```

Additional supporting tables: `users`, `channels`, `comments` (append-only, partitioned by video), `playlists`, `subscriptions`.

## 7. APIs (Representative)
- `POST /v1/videos/upload-url`: returns pre-signed URL + upload session id.
- `POST /v1/videos/{id}/complete`: client signals upload completion → triggers processing.
- `GET /v1/videos/{id}`: metadata fetch.
- `GET /v1/videos/{id}/play`: returns manifest URL, playback token.
- `GET /v1/feed/home`: personalized recommendations.
- `GET /v1/search?q=...`: full-text search with filters.
- `POST /v1/videos/{id}/like`: engagement update (async counters).

## 8. Critical Workflows

### 8.1 Video Upload
1. Client authenticates and requests upload session.
2. Upload Service issues pre-signed URLs; client uploads in parallel chunks with retries.
3. Client notifies completion → Upload Service validates checksum, stores metadata, emits `VideoUploaded`.
4. Orchestrator enqueues transcoding job; metadata state `PROCESSING`.
5. Transcoder produces renditions, uploads manifests, updates state `READY`, emits `VideoReady`.
6. Notification Service alerts subscribers; Search/Recommendation pipelines ingest metadata.

### 8.2 Playback
1. Player requests `/videos/{id}/play`; Playback Service validates status and rights.
2. Service returns manifest URL + token; player fetches manifest from CDN.
3. Player selects representation based on ABR; successive TS/Fragment requests served from CDN edge.
4. Player emits watch progress events → Kafka → analytics & recommendations.

### 8.3 Recommendation Refresh
1. Watch events streamed into Kafka topic.
2. Nearline processors update session features, push to Redis/Feature store.
3. Batch jobs recompute co-watch graph nightly and publish to Feature store.
4. Online service assembles candidates and responds to API calls within 100 ms.

## 9. Capacity Planning (MVP Targets)

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| Daily uploads | 50k videos | Avg 500 MB raw ⇒ 25 TB/day |
| Processed storage | ~3× raw | Multiple bitrates, thumbnails, captions |
| Peak concurrent viewers | 200k | Avg 5 Mbps ⇒ 1 Tbps aggregate bandwidth |
| Metadata QPS | 20k reads / 2k writes | Assume 10 reads per viewer session |
| Search QPS | 5k | With caching for top queries |
| Recommendation latency | < 100 ms p95 | Requires in-memory caching |
| Transcoding throughput | 2k jobs/hour | Needs ~200 workers (10 jobs/hour each) |

Lifecycle policies tier older renditions to infrequent access storage after 30 days; raw uploads archived to Glacier after successful processing.

## 10. Scaling & Resilience Strategies
- **Sharding**: Citus shards `videos` by `video_id`; `comments` partitioned by `video_id % N`.
- **Caching**: Redis for hot metadata, signed manifest tokens, personalization results; CDN for static assets and segments.
- **Replication**: Multi-AZ Postgres with read replicas; Elasticsearch across three availability zones; Kafka with RF=3.
- **Failover**: API services deployed multi-region active-active with global load balancing; transcoding active-passive.
- **Backpressure**: Queue depth monitors trigger autoscaling of transcoding workers; circuit breakers prevent overload on Metadata Service.
- **Disaster Recovery**: Daily snapshots to cross-region bucket; regular restore drills; infrastructure-as-code for rapid redeploy.

## 11. Security & Compliance
- OAuth2 + JWT for auth; scopes grant per-resource access.
- All media URLs signed with short-lived tokens; manifests validated for tampering.
- At-rest encryption (S3 SSE, KMS) and in-transit TLS 1.2+.
- Audit logging for administrative actions and moderation decisions.
- GDPR/CCPA workflows: right-to-be-forgotten triggers delete/obfuscation jobs across storage and caches.

## 12. Observability & Operations
- Metrics: ingest latency, transcoding backlog, playback error rate, CDN hit ratio, recommendation latency.
- Logs centralized in ELK/OpenSearch; sampled distributed tracing with OpenTelemetry.
- Alerting: on-call rotation with PagerDuty; SLO dashboards for availability and latency.
- Deployment: GitOps with progressive rollout (canary, blue/green); feature flags for gradual enablement.
- Runbooks: incident response, stuck transcoding job remediation, metadata cache flush.

## 13. Future Enhancements
- Live streaming pipeline with real-time transcoding and chat.
- Monetization (ads, subscriptions) and DRM integration.
- Advanced analytics for creators (audience retention, traffic sources).
- Multi-language captioning and automated translation.
- Edge compute for low-latency uploads in emerging markets.

This design provides a scalable, highly available foundation for a YouTube MVP while leaving room for future expansions such as live streaming, monetization, and richer analytics.

## 14. Trade-offs & Alternatives
- **Relational vs. NoSQL for metadata**: Chose PostgreSQL (Citus) for strong consistency and relational joins (channels, playlists). Could pivot to DynamoDB/Cassandra for lower-latency writes at scale, but would increase application complexity for joins.
- **Batch + nearline recommendations**: Hybrid provides personalization with manageable complexity. Fully real-time ML (online training) increases freshness but requires heavier infra (feature stores, model monitoring).
- **Single-region transcoding**: Simplifies pipeline and reduces cross-region data transfer cost. Alternative is multi-region transcoding for resilience, but would need global job scheduler and deduplication of renditions.
- **Object storage vs. specialized media store**: S3-compatible storage offers durability and cost efficiency. On-prem HDFS or custom storage could reduce egress fees but increases operational burden.
- **HLS/DASH vs. progressive download**: Adaptive streaming improves QoE under varying network conditions, at the cost of more complex pipeline and manifest management.

## 15. Failure Scenarios & Mitigations
- **Transcoding backlog spike**: Autoscale workers based on queue depth; prioritize premium creators; fall back to lower-resolution renditions first.
- **Metadata DB outage**: Use read replicas for failover; API switches to cached metadata with degraded consistency; writes queued until master restored.
- **CDN cache miss storm**: Monitor origin throughput; pre-warm popular manifests; use multi-CDN failover.
- **Corrupted upload**: MD5 checksum validation; quarantined raw asset; notify creator to re-upload.
- **Recommendation service degradation**: Intelligently degrade to trending + subscribed feeds; circuit breaker to protect downstream data stores.
- **Search reindex failure**: Retain dual clusters during reindex; use blue/green switch; backfill from CDC logs.
- **Regional outage**: Global load balancer drains traffic to healthy region; cross-region read replicas promote; background jobs rescheduled.

## 16. Testing & Rollout Strategy
- **Unit & Integration Tests**: Services validated with contract tests against API Gateway schemas; use localstack/minio for storage mocks.
- **Load Testing**: Synthetic traffic for upload and playback using Locust/K6; ensure 50th/95th latency targets met; run pre-release and continuously.
- **Chaos Engineering**: Fault injections (kill transcoding worker, introduce latency on DB) to validate resilience and alerting.
- **Canary Deployments**: Progressive rollout via service mesh (e.g., Istio) with automated rollback on SLO breaches.
- **Observability Validation**: Pre-production environments must emit metrics, logs, traces to staging stack; gating criterion before production promotion.
- **Data Quality Checks**: Schema validation and drift detection on Kafka topics; nightly audits on engagement aggregates.

## 17. Operational Readiness Checklist
- Documented runbooks for top 10 incidents (transcoding stuck, DB failover, cache invalidation).
- On-call schedule and escalation procedures established; quarterly game days.
- Security reviews completed (threat modeling, penetration testing, dependency scanning).
- Backup and restore tested monthly; RTO < 1 hour, RPO < 5 minutes for metadata.
- Compliance workflows verified (account deletion, content removal SLAs).

## 18. Appendix: Capacity Math Detail
- **Storage**: 50k uploads/day × 500 MB = 25 TB raw; assuming 3 renditions + audio → 75 TB/day. With 30-day hot retention, ~2.25 PB. Cold tier to Glacier cuts hot storage by ~60%.
- **Transcode Compute**: Average encode time 5× video duration. For 10-minute average video (600s) → 3000s per job. Worker handles ~12 jobs/day if single-threaded; use GPU/parallelization to reach 10 jobs/hour → 200 workers for peak; autoscale based on load.
- **Bandwidth**: 200k concurrent viewers × 5 Mbps = 1 Tbps; with 95% CDN hit rate, origin traffic ~50 Gbps. Ensure cross-region replication to serve failover.
- **API Throughput**: 20k QPS metadata reads; each node handles 2k QPS (with caching). Need 10 nodes + headroom. Redis cluster sized for 200 GB hot set, replication factor 2.
- **Kafka**: Watch event rate 5M/hour (~1.4k/sec); use 24 partitions, RF=3, ensure consumer lag < 5s. Provision i3en instances for storage bandwidth.
- **Elasticsearch**: Index size ~200 GB/day; hot nodes (6× r6g.4xlarge) with 1 primary, 1 replica; ILM policy moves to warm storage after 14 days.

## 19. Interview Walkthrough Plan (45 Minutes)
- **Problem Framing (5 min)**: Clarify scope (no live, no ads), confirm scale targets (MAU, uploads/day, concurrency), surface interviewer goals (MVP vs. full YouTube).
- **High-Level Architecture (10 min)**: Present logical diagram (edge, API, storage, data platform). Highlight request flow for upload vs. playback, call out key services.
- **Deep Dives (15 min)**:
  - Upload & Transcoding pipeline (durability, retries, autoscaling).
  - Playback & CDN strategy (adaptive streaming, manifest control).
  - Metadata/Search/Recommendations interplay (consistency, freshness).
- **Scalability & Reliability (8 min)**: Capacity estimates, sharding, caching, multi-region, failure handling scenarios.
- **Operations & Compliance (4 min)**: Observability, deployment, moderation, GDPR.
- **Wrap-up & Q&A (3 min)**: Summarize trade-offs, mention future roadmap (live, monetization), invite questions.

## 20. Diagram Blueprint (for future visuals)
- **Context Diagram**: Users → CDN/API Gateway → Core Services → Data Stores. Include external dependencies (Auth provider, CDN).
- **Upload Sequence**: Stepwise depiction (client, upload service, object store, queue, transcoder, metadata service). Use mermaid sequence or swimlane diagram.
- **Playback Flow**: Player requesting manifest → Playback Service → CDN origin/edge; include ABR decision loop.
- **Data Pipeline**: Event flow from Kafka topics to stream processors, data lake, feature store, recommendation serving. Useful to illustrate nearline vs. batch.
- **Deployment Topology**: Multi-region clusters, cross-region replication, CDN edges.

## 21. Open Risks & Mitigations
- **Legal Takedown Latency**: Need automated compliance pipeline to guarantee removal within SLA; implement content hashing and geographic blocking.
- **Abuse/Spam**: Rate limits on upload, ML classifiers for spam metadata, human moderation queue capacity.
- **Cost Overruns**: Track cost per minute streamed; implement lifecycle policies, spot instances for transcoding, CDN contract negotiation.
- **Privacy Breach**: Strict IAM boundaries, DLP scans for metadata exports, security automation for secret rotation.
- **Recommendation Bias**: Introduce guardrails (diversity constraints, policy review), monitor fairness metrics.

## 22. Frequently Asked Interview Follow-ups
- **Live streaming support?** Outline delta: ingest via RTMP, low-latency HLS, chat service, viewer synchronization.
- **Multi-region active-active?** Discuss metadata replication (logical decoding), conflict resolution, and transcode job deduplication.
- **Handling viral spikes?** Emphasize autoscaling, proactive CDN prefetch, priority queues for hot content.
- **Data deletion compliance?** Describe delete pipeline orchestrated via Kafka, ensures removal from caches, search index, analytics.
- **Recommendations cold start?** Use trending + editorial mixes, gather initial signals via implicit feedback (impressions).

## 23. References & Further Reading
- Martin Kleppmann, *Designing Data-Intensive Applications* – consistency, stream processing.
- ACM Queue, “YouTube Architecture” articles (historical perspective on scaling video).
- AWS Architecture Blog – best practices for large-scale streaming using S3, CloudFront, MediaConvert.
- Google SRE Workbook – incident response patterns useful for ops readiness.

## 24. Threat Model Snapshot
- **Actors**: External attackers (botnets, credential stuffing), malicious insiders, over-privileged third-party integrations, compromised creators.
- **Assets**: Uploaded media, user PII, access tokens, recommendation algorithms, moderation decisions.
- **Attack Surfaces**:
  - API endpoints (upload, comments) → mitigate with WAF, auth throttling, schema validation.
  - Storage buckets → enforce VPC endpoints, bucket policies, encryption, object-level ACL auditing.
  - CDN hotlinking → signed URLs with short TTL, token binding to IP/session.
  - Lateral movement in Kubernetes → Pod security policies, zero-trust service mesh (mTLS), least-privilege IAM roles.
- **Controls**:
  - Security logging with anomaly detection (SIEM).
  - Secrets management via KMS/HashiCorp Vault; automatic rotation.
  - Regular penetration tests and dependency vulnerability scans (Snyk/Dependabot).
  - Data access governed by RBAC + audit trails.

## 25. Data Retention & Governance
- **Raw Uploads**: Retain for 7 days post-transcoding for recovery; then purge or archive.
- **Processed Renditions**: Active storage 30 days; move long-tail to infrequent access; delete when channel removes content.
- **User Data**: Apply data minimization; store watch history for 24 months, then aggregate/anonymize.
- **Logs & Metrics**: Retain detailed logs 30 days (hot), summaries 1 year (cold).
- **Compliance**: Data catalog (AWS Glue) classifies PII; lineage tracked in metadata store; automated jobs ensure deletion requests propagate to all systems within 30 days.

## 26. Cost Management Considerations
- Implement cost allocation tags by service (transcoding, storage, CDN) for FinOps visibility.
- Use spot instances/preemptible VMs for batch transcoding; automatically checkpoint progress.
- Apply intelligent tiering on S3 for aging content; bulk delete infrequently watched renditions.
- Optimize CDN cache keys and TTLs to maximize hit ratio; negotiate commit contracts for bandwidth discounts.
- Monitor cost per uploaded minute and per streamed minute; trigger alerts on anomalies.
- Evaluate open-source transcoding (FFmpeg) vs. managed services (AWS MediaConvert) based on volume to balance opex vs. capex.

## 27. Globalization & Accessibility
- **Localization**: Metadata stored with locale awareness (titles, descriptions), fallback rules; integrate translation service pipeline for auto-generated captions.
- **Regional Compliance**: Apply geo-blocking, local data residency (deploy metadata replicas in EU for GDPR); ensure lawful intercept readiness.
- **Accessibility**: Provide auto-captioning, allow manual subtitle uploads, support screen readers in UI, ensure contrast and keyboard navigation.
- **Content Delivery**: Leverage multi-CDN strategy routed by geolocation; ensure edge PoPs near high-growth markets; analyze per-region QoE metrics.
- **Time Zones & Formats**: Display publish times localized; schedule releases using UTC internally.

## 28. Observability Pipeline Details
- **Metrics**: Collect via Prometheus scraping sidecars; push to long-term storage (Thanos); define SLOs for key paths (upload, playback, recommend).
- **Tracing**: Use OpenTelemetry instrumentation across services; sample rate dynamically adjusted based on error rate; traces exported to Jaeger/Tempo.
- **Logging**: Structured JSON logs shipped via Fluent Bit to log store with retention policies; sensitive data redacted at source.
- **Analytics Events**: Schema evolution managed via Confluent Schema Registry; events delivered to data lake and real-time analytics (Druid/ClickHouse).
- **Visualization**: Dashboards in Grafana/Looker; executive-level KPIs (MAU, watch time) and operational dashboards (transcoding backlog).
- **Alerting**: Multi-channel alerts (PagerDuty, Slack) with enrichment (runbook links, context traces).

## 29. Product & Engineering Roadmap (12 Months)
- **Q1**: Harden MVP, launch beta; integrate manual moderation tooling; complete cost dashboards.
- **Q2**: Introduce live streaming alpha; expand recommendation models with contextual bandits; roll out automated subtitle translation.
- **Q3**: Monetization pilot (ads infrastructure, revenue reporting); expand to additional regions with local compliance needs; cross-device playback sync.
- **Q4**: Launch community features (stories, shorts); AI-powered content insights for creators; continuous deployment with automated rollback policy.
- Cross-cutting: Security hardening, privacy compliance updates, performance optimization, developer productivity tooling (service templates, CI/CD improvements).

## 30. Closing Summary
This YouTube MVP design delivers a production-ready blueprint balancing rapid feature delivery with scalability, resiliency, and regulatory guardrails. The architecture centers on durable object storage, adaptive streaming via CDN, and a service-oriented control plane backed by robust data pipelines. Supporting sections outline operational maturity (testing, observability, threat modeling), cost and governance practices, and an actionable roadmap enabling future evolution (live, monetization, global expansion). The document equips a Staff+ candidate to articulate trade-offs, respond to follow-ups, and demonstrate end-to-end ownership in an interview setting.

## 31. Service Level Objectives (SLOs)
| Service | SLO | SLI Definition | Notes |
|---------|-----|----------------|-------|
| Upload API | 99.9% success, p95 latency < 400 ms | Ratio of successful `POST /upload-url` calls; latency via histogram | Alerts when 5-minute rolling SLI < 99.5% |
| Transcoding Pipeline | 95% jobs complete < 15 min | Time from `VideoUploaded` event to `READY` state | Separate error budget for VIP creators |
| Playback | 99.95% availability, startup latency < 2s p95 | Availability defined as manifest and first chunk fetch | QoE monitors ingest client metrics |
| Metadata Reads | p95 < 150 ms | `GET /videos/{id}` latency | Cached responses excluded from SLI |
| Recommendations | p95 < 120 ms | Latency for `GET /feed/home` | Track click-through and satisfaction |

## 32. Organizational Considerations
- **Team Topology**: Vertical pods per surface (Creator, Viewer, Platform), supported by horizontal infra teams (Video Platform, Data Platform, SRE, Security).
- **Ownership Boundaries**: Each service has DRIs for uptime metrics; runbooks and on-call rotation defined. Shared services (Kafka, Postgres) owned by platform teams with clear interfaces.
- **Development Workflow**: Trunk-based development with feature flags; mandatory design reviews for cross-team dependencies; weekly tech review forum to align on architecture decisions.
- **Governance**: API standards (OpenAPI/Protobuf), coding guidelines, shared libraries for observability/auth. Architecture review board for significant changes (e.g., new data store adoption).

## 33. Interview Cheat Sheet
- **Key Messages**: MVP supports upload→transcode→serve, metadata/search/recommendation loops, resilience via queues/cache/CDN, strong observability and governance.
- **Trade-off Talking Points**: SQL vs NoSQL metadata, multi-region strategy, recommendation freshness vs complexity, cost vs quality for transcoding.
- **Critical Metrics**: Upload latency, transcode throughput, CDN hit rate, watch time growth, cost per streamed minute.
- **Failure Stories**: Describe handling of transcoding backlog, metadata outage, CDN issues. Emphasize detect→mitigate→prevent loops.
- **Future Evolution**: Live streaming, monetization, personalization model sophistication, ML ops maturity.

## 34. Compliance Workflow Architecture
- **Policy Engine**: Central rule service that evaluates uploads/comments against regional policies; executes blocking, age-gating, or monetization restrictions.
- **Audit Trail**: Immutable log (append-only store, e.g., QLDB) capturing moderation decisions, reviewer identity, timestamps for legal defensibility.
- **User Requests**: GDPR/CCPA portal triggers workflow orchestrator (Step Functions/Temporal) to cascade deletions across metadata, storage, search index, analytics tables.
- **Regulatory Reporting**: Scheduled jobs aggregate takedown metrics, response times, geographical breakdown; export to BI tools and compliance team dashboards.
- **Access Reviews**: Quarterly automated checks ensure least-privilege access to sensitive operations; integrate with IAM governance (SailPoint).

## 35. ML Operations Considerations
- **Model Lifecycle**: Versioned models stored in ML registry (MLflow/SageMaker); CI/CD pipelines validate performance before deployment.
- **Feature Management**: Feature store (Feast) with both online (Redis) and offline (Parquet) storage; ensures training/serving skew minimized.
- **Observability**: Monitor model drift, data quality, and fairness metrics; alerts trigger retraining workflows.
- **Serving Architecture**: Containerized inference services with auto-scaling; A/B testing framework (feature flagging) for gradual rollout.
- **Feedback Loop**: Continuous ingestion of watch outcomes and user feedback to update labels; ensure privacy compliance before using personal data.

## 36. Product Backlog Prioritization
- **Tier 0 (Must Have)**: Upload reliability improvements, transcoding SLA enforcement, playback QoE monitoring, moderation tooling enhancements.
- **Tier 1 (Should Have)**: Personalized home feed tuning, subtitle translation quality, creator analytics dashboards, auto-scaling cost optimization.
- **Tier 2 (Could Have)**: Collaborative playlists, social sharing integrations, AI-powered chapter generation, VR/360 video support.
- **Evaluation Criteria**: Impact on user retention, cost efficiency, regulatory risk, engineering complexity, alignment with OKRs.
- **Review Cadence**: Quarterly roadmap review with stakeholders; monthly backlog grooming with cross-functional leads.
