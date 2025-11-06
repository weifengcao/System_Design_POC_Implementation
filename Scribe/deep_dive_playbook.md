# Deep Dive Playbook

Potential interviewer follow-ups and how to navigate them quickly.

## 1. Step Boundary Detection & ML
- **Prompt**: “How do you decide what constitutes a step?”  
- **Answer**: Combine heuristics (time gaps, DOM tree changes, navigation events) with ML classifier trained on labeled sessions. Mention features: DOM node stability, input type, scroll context.  
- **Trade-offs**: pure heuristics are fast but brittle; ML improves accuracy but adds inference cost. Stress fallback logic and experimentation framework using offline replays.

## 2. Redaction & Privacy Controls
- **Prompt**: “How do you ensure sensitive data isn’t leaked?”  
- **Answer**: Client-side masking (DOM selectors, regex), server-side PII detection (OCR + NLP), tenant policy enforcement. Describe redaction pipeline, human override, audit logs.  
- **Escalation**: Discuss CMK integration, per-tenant redaction rules, right-to-be-forgotten job.

## 3. Multi-Region Failover
- **Prompt**: “What happens if a region goes down?”  
- **Answer**: Control plane active-active; ingestion uses geo-aware routing. If data plane fails, fail traffic to warm standby region. Guide metadata replicated via Aurora Global Database; DynamoDB global tables for content; S3 cross-region replication for media. Outline RTO/RPO (<5 min with async replication).  
- **Caveat**: Live sessions in affected region pause; agent retries to alternative region.

## 4. Real-time Collaboration Consistency
- **Prompt**: “How do you avoid conflicts during co-editing?”  
- **Answer**: Use CRDT/OT (Automerge-like) with vector clocks per client. Change log persisted to append-only store for auditing. Periodic snapshots to Document DB. Mention handling offline edits, merging on reconnect.

## 5. AI Service Reliability
- **Prompt**: “What if the AI provider is unavailable or latency spikes?”  
- **Answer**: Circuit breaker + fallback heuristics (template-based summaries). Queue requests via asynchronous workers; use caching of prior AI outputs. For enterprise, offer on-prem model hosting. SLO monitoring triggers degradation mode (skip optional features).  
- **Cost Controls**: Rate limit per tenant, use distillation for common languages.

## 6. Tenant Isolation & RBAC
- **Prompt**: “How do you prevent data leakage between tenants?”  
- **Answer**: Tenant ID embedded in every resource key; row-level filtering at service layer. Use IAM roles scoped per tenant for S3/Dynamo. Mention dedicated clusters option and VPC peering for regulated clients.  
- **RBAC**: Explain role hierarchy, attribute-based conditions, fine-grained share links with expiring tokens.

## 7. Search Scaling & Relevance
- **Prompt**: “How do you handle search at scale?”  
- **Answer**: OpenSearch clusters sharded by tenant_id hash; index includes OCR text, tags, app context. For large tenants, dedicated indexes. Use synonyms for app terminology, ranking signals (view count, recency). Periodic re-index for updated guides.  
- **Latency**: Cache popular results; highlight partial updates via Kafka CDC.

## 8. Recording Agent Performance & Security
- **Prompt**: “How do you keep agents lightweight and secure?”  
- **Answer**: Native capture uses OS APIs with sandboxing; minimal CPU (<5%) by batching events. Secure auto-updates signed with code certificate. Attestation via device ID + checksum. Provide admin controls (policy distribution, remote disable). Discuss offline mode and disk encryption.

## 9. Analytics & Insights
- **Prompt**: “How do teams get usage insights?”  
- **Answer**: Stream view events, edits, shares into analytics lake. Pre-compute per-tenant dashboards (Snowflake) for top guides, adoption trends. Offer APIs/webhooks for BI tools. Tie back to design doc’s analytics section.

## 10. Extensibility / Integrations
- **Prompt**: “How do you integrate with other tools?”  
- **Answer**: Webhooks on publish/update, REST APIs for guide export, connectors for Confluence/Notion with OAuth. SDK for embedding interactive guides. Highlight multi-tenant API throttling and audit logging.

Keep references handy: `design.md` for architecture/storage, `flows.md` for sequences, `talk_track.md` for pacing.
