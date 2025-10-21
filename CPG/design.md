# CPG Procurement Copilot – Staff+ Design Document

## 0. Executive Summary
CPG (Cognitive Procurement Guide) augments enterprise procurement with an autonomous, trustable copilot. Deterministic microservices (PO intake, supplier registry, compliance, analytics, communications) guarantee transactional integrity and regulatory compliance. A retrieval‑augmented multi‑agent system performs high-variance reasoning: supplier discovery, negotiation, strategy synthesis, and continuous learning. A graph-backed knowledge fabric acts as the shared blackboard linking structured system-of-record data with unstructured context (policies, transcripts, market intel). The platform is orchestrated via event-driven workflows with guardrails, human checkpoints, and comprehensive observability.

## 1. Background & Context
- Enterprises today run serial, manual RFQ cycles, with repetitive email exchanges, spreadsheet tracking, and tribal knowledge.
- Microservice transformations have improved ERP interfaces but still rely on human decision makers for supplier selection and negotiation.
- Recent LLM advances (planning, tool-use, retrieval) enable autonomous agents to operate over complex, semi-structured domains.
- Competitors (e.g., Waystation AI) focus on narrow verticals; CPG targets a generalized, multi-industry solution while preserving auditability and control.

### Stakeholders
- Procurement leadership (CPO, category managers)
- Finance and compliance officers
- SRM / supplier-relationship teams
- ML/AI platform team responsible for model governance
- SRE / platform engineering for infrastructure & reliability

## 2. Goals & Non-Goals
### Goals
1. Automate sourcing workflows (intent extraction → supplier discovery → negotiation → recommendation) while retaining human oversight.
2. Provide explainable decisions (policy citations, negotiation transcripts, supplier dossiers).
3. Support multi-industry categories and multi-tenant deployments.
4. Integrate with existing ERP/PRM systems via APIs and events.
5. Enable rapid experimentation with prompts, agents, retrieval schemas, and toolchains.

### Non-Goals
- Procure-to-pay settlement (invoicing, payment execution).
- Replace ERP master data management; instead consume and enrich.
- Deliver a full production UI. We provide a console/API for operators and leave final UI to downstream teams.
- Real-time bidding marketplace (considered future work).

## 3. User Stories
1. **Category Manager** submits a PO and receives an AI-prepared shortlist, negotiations, and a recommendation with supporting evidence.
2. **Compliance Officer** reviews AI negotiations and sees policy checks plus flagged issues requiring human approval.
3. **Supplier Liaison** monitors outbound comms and can step in when AI escalates.
4. **Data Scientist** deploys a new negotiation strategy, compares metrics, and rolls back if KPIs regress.

## 4. Requirements
### Functional
1. Ingest POs from ERP (REST/SFTP/stream) and normalize into canonical schema.
2. Maintain supplier registry with search, risk scoring, diversity tags, certification history.
3. Persist policies, negotiations, and market intel in a shared knowledge fabric (vector + graph).
4. Execute agent workflow: Planner → Sourcing Scout → Compliance Sentinel → Negotiator (with Critic validation) → Insights Reporter.
5. Provide human checkpoints and ability to pause/resume workflows.
6. Expose APIs/events for downstream systems (ERP updates, dashboards, Slack notifications).
7. Capture detailed audit logs (decisions, messages, retrieval context, tool calls).

### Non-Functional
1. Availability: 99.9% for core services and event bus; 99.5% for agent execution plane.
2. Latency: <500 ms P95 for microservice APIs; <300 ms retrieval P95; <5 min end-to-end sourcing SLA under normal load.
3. Multi-tenant isolation with per-tenant encryption keys and data residency controls.
4. Scalability: 500 concurrent sourcing events, 2k supplier threads, 100M emails/year.
5. Observability: distributed tracing, metrics (token usage, success rates), log correlation IDs.
6. Security: RBAC/ABAC, secrets management, DLP, guardrails against prompt injection/PII leakage.

## 5. Assumptions & Scale
- Average enterprise: 300 sourcing events/month, 10–20 suppliers each.
- Knowledge corpus: 100k documents (~50 GB) + streaming updates from ERP/market data; vector index growth 10 GB/year.
- LLM budgets: baseline 8k context, extendable to 32k for complex negotiations.
- Agents run stateless worker containers; underlying LLM provider can be SaaS or self-hosted.

## 6. Architecture Overview
```
ERP/CRM Systems ──> PO Service ──┐
                                 │     ┌──────────────┐
Supplier Data Feeds ──> Supplier Registry ──┐        │  Agents / Workflows │
                                              ├──> Event Bus ─┤ (Planner, Scout,
Policies/Docs ──> Ingestion ──> Graph RAG ───┘        │  Compliance, Negotiator,
                                                      │  Critic, Reporter)      │
Temporal Workflow Engine <────────────────────────────┘
      │                                               │
      ▼                                               ▼
Compliance Ledger / Analytics / Messaging        ERP/BI Integrations
```
- Microservices own authoritative data; emit CDC events for the knowledge plane.
- Agents subscribe to events, perform retrieval/tool calls, and publish follow-up events.
- Temporal orchestrates macro state and human checkpoints.
- Graph RAG combines vector search + property graph with provenance metadata.

## 7. Component Detail
### Microservices
1. **PO Service**
   - PostgreSQL, REST/gRPC, CDC via Debezium.
   - Validates schema, stores enrichments & approvals.
2. **Supplier Registry**
   - PostgreSQL + Redis cache; risk scoring pipelines; exposes `/suppliers/search`.
   - Emits `supplier.updated` events for RAG refresh.
3. **Compliance Engine**
   - OPA policy bundles, audited via QLDB/WORM.
   - API: `POST /compliance/check`.
4. **Analytics Service**
   - Built on Snowflake/BigQuery; dashboards via Looker/Mode.
5. **Messaging Service**
   - Sends outbound email/chat with provider integration (SES/SendGrid/Slack).
   - Enforces rate limiting, DLP, templating.

### Knowledge Plane
- **Vector Store:** Pinecone/Weaviate with embedding metadata (version, TTL).
- **Graph Store:** Neo4j/Neptune modeling suppliers, POs, negotiations, policy clauses.
- **Keyword Index:** OpenSearch for deterministic lookups.
- **Retrieval API:** Hybrid (semantic + graph) with citation tracking and freshness scoring.

### Agent Mesh
- **Planner Agent:** triggered by `po.created`; constructs plan and seeds Temporal workflow.
- **Sourcing Scout Agent:** consumes `task.plan.completed`; combines supplier registry search with RAG justifications; writes shortlist.
- **Compliance Sentinel Agent:** consumes `supplier.shortlist.created`; checks policies; emits success/failure.
- **Negotiator Agent:** consumes `compliance.approved`; orchestrates outreach rounds via Messaging Service while storing transcripts in RAG.
- **Critic Agent:** validates negotiation results; re-runs policy checks using deterministic engine before final output.
- **Insights Reporter Agent:** composes final recommendation, KPIs, citations; publishes `report.ready`.
- **Escalation Agent (future)**: handles `compliance.failed` or `negotiation.validation_failed`, routes to human queue.

### Workflow Engine (Temporal/Camunda)
- State machine per PO; tasks map to agent stages.
- Supports retries, backoff, human approval tasks, and manual overrides.

### Event Bus (Kafka/Redis Streams)
- Topics with schema-registry managed payloads.
- Idempotency keys pattern: `${PO_ID}::${stage}::${round}`.
- Dead-letter queues for manual intervention.

## 8. Data Model Highlights
- **PO**: `po_id`, category, region, quantity, budget ceiling, timeline, required_certs, notes, approvals.
- **Supplier**: `supplier_id`, categories, regions, diversity tags, certifications, risk score, benchmark price index, contact info.
- **Negotiation Edge**: `(PO) -[:OFFERED {price, round, timestamp}]-> (Supplier)`, `(Supplier) -[:RESPONSE]-> (Offer)`.
- **Policy Nodes**: `PolicyClause` nodes linked to compliance checks.
- **Retrieval Metadata**: `embedding_id`, `source_service`, `version`, `expires_at`.

## 9. Workflow (Sequence)
1. **PO Intake**
   - ERP → `po_service.create` → emit `po.created`.
   - Planner Agent retrieves similar cases via RAG, seeds workflow tasks.
2. **Supplier Discovery**
   - Sourcing Scout queries `supplier_registry.search`, attaches citations (RAG).
   - Shortlist stored via API + event `supplier.shortlist.created`.
3. **Compliance**
   - Compliance Sentinel calls `compliance_engine.check`.
   - On failure: emit `compliance.failed`, temporal step awaits human resolution.
4. **Negotiation Loop**
   - Negotiator Agent sends emails via Messaging, updates RAG with transcripts.
   - Supplier responses via outbound webhook → `negotiation.response.received` event; agent iterates.
5. **Validation & Reporting**
   - Critic replays outcome vs policy; if pass, reporter composes memo (KPIs, citations).
   - Insights Reporter publishes `report.ready`; Temporal signals completion.
6. **Feedback**
   - Analytics pipeline updates savings metrics; CDC triggers RAG refresh.
   - Prompt/tool versions logged in experiment registry.

## 10. Reliability & Fault Tolerance
- Event bus retries with exponential backoff; messages acked only after successful handling.
- Temporal checkpoints allow restart from latest successful stage.
- Idempotency registry prevents duplicate writes.
- Critic Agent + guardrails reduce hallucination risk.
- Manual override tasks for compliance/negotiation issues.
- Disaster recovery: cross-region replication for databases, RAG, and event log.

## 11. Security & Compliance
- Tenant isolation enforced at DB (schema separation) and vector namespaces.
- Field-level encryption (KMS) for sensitive PO fields.
- SSO/OIDC for agents’ tool invocations; scoped credentials per agent.
- DLP scanning for outbound messages; audit ledger stores every action with signer identity.
- Regular red-team exercises targeting prompts, tool APIs, and network boundaries.

## 12. Observability
- Tracing: OpenTelemetry instrumentation across services and agents (trace context propagated via events).
- Metrics: token usage, agent SLA, retries, savings, compliance issues.
- Logging: structured logs with `po_id`, `agent`, `event_id`.
- Diagnostics: replay service fetches stored context (plan, retrieved docs, emails) for debugging.

## 13. Testing & Validation Strategy
- Unit tests for services, retrieval components, and agent tool adapters.
- Simulation harness for end-to-end workflows (synthetic supplier responses).
- Chaos experiments: message loss, delayed responses, service outages.
- Guardrail evaluation: prompts fuzzed for injection, PII leakage tests.
- Pilot rollout with shadow mode: agents produce recommendations while humans execute; compare metrics before full automation.

## 14. Deployment Plan
1. **Phase 0 – Sandbox**: current in-memory prototype used for developer exploration.
2. **Phase 1 – Foundational Services**: containerized microservices + Kafka + Temporal in dev environment.
3. **Phase 2 – Agent Integration**: connect agents to dev environment with real retrieval and messaging sandboxes.
4. **Phase 3 – Limited Pilot**: integrate with staging ERP; enable human-in-loop; monitor KPIs.
5. **Phase 4 – Production Rollout**: multi-region deployment, SLO monitoring, incident response runbooks.

## 15. Trade-offs & Alternatives
- **Hybrid vs Monolithic Agent**: we accept additional infra complexity to maintain auditability and regulatory compliance.
- **Graph RAG vs pure Vector**: graph modeling increases development cost but enables multi-hop reasoning and explainability.
- **Temporal + Event Bus vs Single Orchestrator**: more moving parts but gives resilience, visibility, and human intervention support.
- **Agent-per-function vs Mega-agent**: specialization simplifies prompts & guardrails; at cost of coordination overhead.

## 16. Open Questions
1. Which LLM provider(s) and deployment model (SaaS vs self-hosted) meet latency, cost, and compliance requirements?
2. How aggressively should we prune/TTL knowledge entries to balance cost and freshness?
3. What thresholds trigger automatic escalation vs human review?
4. How to score negotiation agent performance beyond savings (e.g., supplier sentiment, lead-time reliability)?
5. What level of customizability do tenants need for policy/strategy configuration?

## 17. Future Enhancements
- Automated auction/tendering across suppliers with real-time bidding agent.
- Meta-agent optimizing negotiation strategies using reinforcement learning.
- Federated graph updates across tenants with differential privacy.
- Multimodal retrieval (CAD drawings, images) integrated into negotiation reasoning.
- Voice / conversational interface for supplier interactions.

---
This document now serves as the Staff+ reference for engineering, platform, and procurement teams to align on architecture, requirements, and implementation roadmap.

