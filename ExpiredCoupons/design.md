# ExpiredCoupons System Design

## 1. Problem Statement
ExpiredCoupons must identify, process, and deactivate 10M+ coupons approaching expiration daily while notifying stakeholders (customers, merchants, marketing teams) and freeing inventory or budget allocations. The platform ingests coupon definitions, usage telemetry, and partner updates; orchestrates bulk expiration workflows; and integrates with downstream systems (e-commerce, CRM, BI). The solution needs high throughput, strong consistency for redemption prevention, and observability to ensure no coupon remains active after expiration.

## 2. Goals & Non-Goals
- **Goals**
  - Detect coupons nearing expiration (e.g., within next 24–48 hours) and process them in batches or streams.
  - Atomically deactivate coupons across online/offline channels ensuring zero post-expiration redemption.
  - Notify customers/merchants via email/SMS/app push about impending expiration, including win-back campaigns.
  - Provide dashboards and APIs for operations to monitor backlog, success rates, and anomalies.
  - Maintain auditable history of coupon lifecycle events for compliance and reconciliation.
- **Non-Goals**
  - Full coupon creation or offer recommendation system.
  - Payment processing or loyalty point settlement.
  - Real-time personalization engine for marketing (only hooks provided).

## 3. Personas & Use Cases
- **Marketing Ops**: schedule reminders, ensure campaigns retire on time.
- **Merchants/Partners**: view their coupon status, request extensions.
- **Customer Support**: audit expired coupon history during disputes.
- **Platform SRE**: monitor pipeline health, respond to failures.
Key use cases: nightly expiration sweep, near-time streaming updates, forced manual expiry, extension approvals, notification fallback, BI exports.

## 4. Requirements
- **Functional**
  - Ingest coupon definitions (ID, validity window, merchant, channels, inventory) from offer management system.
  - Track coupon state transitions (issued, reserved, redeemed, expired, extended).
  - Identify approaching expirations via scheduler (cron + streaming events).
  - Execute deactivation across multiple systems (e-commerce API, POS proxies, partner APIs).
  - Trigger customer/merchant notifications with templating and throttling.
  - Support manual overrides & bulk upload for extension or cancellation.
  - Expose APIs for coupon state queries, reporting, and audit logs.
- **Non-Functional**
  - Throughput: process 10M coupons in under 4 hours (target 10k ops/sec).
  - Latency: ensure expiration propagates to redemption systems within 1 minute of scheduled time.
  - Scalability: handle seasonal spikes (Black Friday) with 5x load.
  - Reliability: 99.95% availability for redemption-blocking services.
  - Consistency: at-least-once delivery on deactivation commands with idempotency guarantees.
  - Security: RBAC, data encryption, GDPR compliance for user notifications.

## 5. Assumptions & Scale
- Coupon metadata size ~1 KB; 50M active coupons at any time (~50 GB in primary store).
- Daily delta: 10M expiring; 2M near-term extensions; 5M notifications.
- 100 integration endpoints (internal + partner) with varying SLAs.
- Notification channels capacity: Email 20k/min, SMS 5k/min, Push 100k/min.
- 30 OPS users, 10K merchants, 100M consumer accounts.

## 6. High-Level Architecture
1. **Ingestion Layer**
   - APIs/webhooks for coupon creation updates.
   - Batch imports via SFTP/CSV to object storage (S3/GCS) processed by ETL.
   - Streaming bus (Kafka/PubSub) for real-time state changes (redemptions, cancellations).
2. **Core Services**
   - **Coupon Catalog Service (CCS)**: CRUD for coupons, stores metadata in scalable RDBMS or document store with partitioning (e.g., Aurora/MySQL with sharding by merchant or offer family).
   - **State Transition Service (STS)**: ensures legal state machine transitions; writes event log (Kafka) and audit store (immutable log).
   - **Expiration Orchestrator**:
     - Batch scheduler (Airflow/Temporal) to enqueue expiration jobs by time bucket.
     - Near-real-time stream processor (Flink/Spark Structured Streaming) for continuous window evaluation.
   - **Deactivation Service**: fan-out to redemption systems (internal API, partner adapters) with retries/backoff.
   - **Notification Service**: orchestrates messaging via provider APIs with templating and throttling.
   - **Ops Console Service**: UI/API for overrides, monitoring, reporting.
3. **Data Platform**
   - Data lake for historical state events (S3 + Iceberg).
   - Analytics warehouse (Snowflake/BigQuery) for BI dashboards.
   - Stream analytics (Flink SQL) for real-time metrics (expirations/min).
4. **Integration Layer**
   - Adapter microservices per partner to handle authentication, rate limits, idempotency keys.
   - Event-driven webhooks to notify partners of expirations or extensions.
5. **Experience Layer**
   - Internal React UI for operations/merchants.
   - External REST/GraphQL APIs for merchants/partners to query statuses.

## 7. Data Flow
1. **Coupon Ingestion**: Offer system sends new coupon to CCS via API. CCS persists metadata, emits `coupon.created`.
2. **State Updates**: Usage events (reserve/redeem) arrive via Kafka; STS validates transitions, updates stash, emits `coupon.state_changed`.
3. **Expiration Scheduling**: Airflow job reads coupons expiring next 48h, groups by expiration timestamp, writes job bundles to Kafka topic `coupon.expiration-enqueue`.
4. **Processing**: Expiration Orchestrator consumes jobs, loads coupon batches from CCS, marks `pending_expiration`, and invokes Deactivation Service.
5. **Fan-out**: Deactivation Service publishes commands to connectors (e-commerce, POS). Idempotent operations ensure safe retries. Upon success, STS sets state to `expired`, emits event.
6. **Notifications**: Notification Service triggers templated messages using `coupon.pending_expiration` and `coupon.expired` events, logs deliveries, handles retries/DLQ.
7. **Monitoring & BI**: Metrics pipeline consumes events, aggregates in time-series DB (Prometheus + Thanos) and data warehouse for dashboards.

## 8. Detailed Components
- **Coupon Catalog Service**
  - Partition by expiration date for efficient range scans.
  - Secondary indexes on merchant, campaign, channel.
  - Uses write-through cache (Redis) for high read QPS.
  - Supports TTL metadata to allow auto-archival post-expiry.
- **State Transition Service**
  - Implements finite state machine with validation rules (e.g., cannot extend expired coupon without override).
  - Uses distributed lock or compare-and-set to ensure atomic transitions with CCS.
  - Maintains append-only event log in Kafka; persisted to audit store (Cassandra/QLDB).
- **Expiration Orchestrator**
  - Jobs include metadata: coupon IDs, merchant priority, required channels.
  - Uses Temporal workflow for retries with exponential backoff and compensation (e.g., re-enable coupon on partial failure).
  - Supports dynamic reprioritization (e.g., high-value merchants first).
- **Deactivation Connectors**
  - Each connector encapsulates partner-specific logic with circuit breakers.
  - Track per-partner SLAs and quotas; fallback to manual queue if failures exceed threshold.
  - Provide synchronous ack when partner confirms; asynchronous ack via webhook or callback handled via state machine update.
- **Notification Service**
  - Template engine (MJML/Handlebars) with localization.
  - Integrates with providers (SES, Twilio, Firebase). Prioritizes push/email; SMS as fallback.
  - Offers consent management and quiet hours.
- **Ops Console**
  - Displays backlog, failure queues, partner health, notification status.
  - Allows manual override with audit trails and approval workflow.
- **Analytics**
  - Real-time metrics: coupons processed/min, failure rate, SLA adherence.
  - Historical: redemption vs expiration curves, merchant performance, campaign ROI.

## 9. Storage Strategy
- **Operational Stores**
  - Aurora/MySQL (coupons metadata) with read replicas.
  - Redis (cache), Kafka (event log), Cassandra/QLDB (audit), Elasticsearch/OpenSearch (searchable coupons).
  - TimescaleDB/Prometheus (metrics), DynamoDB for high write idempotency keys.
- **Analytical Stores**
  - S3 + Iceberg/Delta for raw and curated data.
  - Snowflake/BigQuery for BI and machine learning insights (e.g., churn prediction).
  - Feature store optional for advanced prioritization models.
- **Backups & DR**
  - Automated snapshots, cross-region replication, point-in-time recovery.

## 10. Scaling & Performance
- Batch processing: partition coupons by expiration time (hourly buckets) enabling parallel workers (100+ pods) to process ~100k coupons/min each.
- Leverage Kafka partitions keyed by coupon ID to maintain ordering per coupon.
- Adaptive rate limiting per partner connector; degrade gracefully by prioritizing critical channels.
- Use eventual consistency for notifications but strong consistency for redemption block paths (distributed transactions or asynchronous compensation).
- Cache invalidation on expiration events to avoid stale reads.
- Consider using Change Data Capture (CDC) from CCS to drive streaming pipeline.

## 11. Reliability & Observability
- Multi-AZ deployment; cross-region DR for critical services.
- SLOs defined for expiration propagation, notification success, connector availability.
- Observability stack: Prometheus metrics, Grafana dashboards, Jaeger tracing, ELK logging.
- Alerting for backlog growth, partner failures, notification bounce spikes.
- Runbook automation for expired coupon backlog drain, partner outage failover.

## 12. Security & Compliance
- SSO (SAML) for ops console; RBAC/ABAC to restrict partner access.
- Encrypt data at rest (KMS) and in transit (mTLS).
- PII handling for customer contact info; respect opt-out lists.
- Audit trail immutable store; provide compliance exports (GDPR right to be forgotten).
- Secret management via Vault/Secrets Manager.

## 13. Deployment & Lifecycle
- Infrastructure as code (Terraform/CloudFormation).
- Services deployed on Kubernetes/ECS with GitOps (ArgoCD).
- CI/CD with blue/green for orchestrators and connectors. Canary rollouts with synthetic coupons to validate flow.
- Backfill tooling for migrating historical coupons or recovering from outages.
- Feature flags for new connectors or notification campaigns.

## 14. Risks & Mitigations
- **Partner API Failures**: Retry with exponential backoff, escalate to manual queue, maintain SLA dashboards.
- **Data Skew/Hot Partitions**: Partition by hashed coupon ID + expiration time to distribute load.
- **Clock Drift**: Use centralized time service (NTP), avoid relying on client clocks.
- **Notification Failures**: Multi-provider strategy, delayed retries, fallback channel.
- **Compliance Violations**: Automated checks before sending notifications, built-in policy engine.

## 15. Future Enhancements
- Predictive churn models to prioritize reminder campaigns by likelihood of redemption.
- Self-service portal for merchants to configure expiration workflows.
- Generative AI for personalized reminder content.
- Real-time redemption blocking using inline API gateway with caching.
- Integrating blockchain-based coupon verification for high-value partners.

