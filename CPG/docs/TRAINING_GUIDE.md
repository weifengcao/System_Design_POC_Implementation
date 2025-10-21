# CPG Procurement Copilot – New Hire Training Guide

Welcome to the CPG procurement copilot project. This training guide is designed for new graduates who may have limited experience with distributed systems, AI agents, and retrieval-augmented generation (RAG). The goal is to help you ramp up quickly, understand the codebase, and contribute new features with confidence.

---

## Table of Contents
1. Project Overview
2. Architecture Rationale (Why This Hybrid Approach)
3. Core Concepts Refresher
4. Repository Tour & Code Organization
5. Runtime Flow (Step-by-Step)
6. Service Layer Deep Dive
7. Agent Layer Deep Dive
8. Knowledge & Retrieval Pipeline
9. Eventing & Workflow Orchestration Details
10. Coding Standards, Testing Strategy & Observability
11. Worked Example: Adding a New Agent
12. Advanced Topics & Research Directions
13. FAQs & Further Resources

---

## 1. Project Overview

CPG combines:
- **Microservices**: deterministic REST/gRPC services handling core procurement data (purchase orders, suppliers, compliance, analytics, messaging).
- **Multi-Agent System**: specialized AI agents (planner, sourcing scout, negotiator, critic, etc.) orchestrated through an event bus and workflow engine.
- **Graph RAG Memory**: retrieval-augmented store that blends semantic search with graph relationships (supplier history, policies, negotiations).

The architecture balances reliability (microservices), adaptability (agents), and explainability (graph RAG) so procurement teams can automate complex sourcing while staying compliant.

---

## 2. Architecture Rationale (Why This Hybrid Approach)

Traditional microservice platforms give us reliability, strict schemas, and transactional guarantees. However, procurement workflows involve ambiguous inputs (PDF specifications, emails, policies) and non-linear reasoning (negotiation strategies, compliance nuances). We therefore combine two paradigms:

1. **Deterministic microservices** guard states with hard guarantees. They act as the *source of truth*, enforce compliance, and integrate with ERP/BI systems.
2. **Agentic reasoning layer** provides adaptability. Agents run LLM-backed reasoning, orchestrate tasks, and interact via tools.
3. **Graph-enhanced RAG memory** bridges both worlds with explainable grounding. It stores structured links (supplier ↔ policy ↔ negotiation outcomes) and semantic embeddings, so agents can justify decisions with citations.

This decomposition is intentional:
- Keeps human auditors confident because all writes go through services and every recommendation references policy clauses.
- Allows rapid experimentation—agents/prompt changes don’t destabilize transaction logic.
- Supports multi-tenancy: services enforce isolation; RAG namespaces keep tenant data separate.
- Scales horizontally: agents are stateless workers consuming events; services behind load balancers; RAG indexes partitioned per tenant/domain.

## 3. Core Concepts Refresher

### Microservices
- Each service owns a specific domain: `POService`, `SupplierService`, `ComplianceService`, etc.
- Services expose APIs used by agents; in our demo they’re in-memory but mirror real API designs.

### Agents
- Agents are small programs that react to events, query services/RAG, and publish follow-up events.
- In the demo they follow a sequential sourcing pipeline: planner → scout → compliance sentinel → negotiator → critic → reporter.

### Event Bus & Workflow
- Agents communicate asynchronously through the `EventBus` (a simplified stand-in for Kafka/Redis Streams).
- `WorkflowEngine` acts like Temporal – tracking task states and enabling checkpoints & human-in-loop hooks.

### RAG (Retrieval-Augmented Generation)
- We embed policies, supplier dossiers, negotiation snippets into a vector store and a lightweight graph.
- Agents retrieve relevant context before generating actions/emails so decisions are grounded.

---

## 4. Repository Tour & Code Organization

```
CPG/
├── data/                  # Fixture data for knowledge base and POs
├── docs/                  # Documentation (this guide, design doc)
├── src/
│   ├── agents/            # Agent implementations
│   ├── infrastructure/    # Event bus, workflow, guardrails, idempotency
│   ├── pipelines/         # CDC and retrieval evaluation stubs
│   ├── retrieval/         # Hybrid retriever and adapters
│   ├── services/          # Mock microservices
│   ├── knowledge.py       # Vector + graph memory store
│   └── coordinator.py     # Orchestrator glue logic
├── design.md              # Staff+ system design document
├── demo.py                # CLI entrypoint
└── README.md              # Quick start summary
```

### Key Files & Why They Matter
- `design.md`: Staff+ design decisions, constraints, trade-offs, and future roadmap.
- `docs/TRAINING_GUIDE.md`: this document—bookmark for onboarding.
- `src/coordinator.py`: orchestrates services, workflow engine, event bus, retriever, and registers agents. Think of it as “main()” for the platform.
- `src/agents/*.py`: each file implements a specific agent with clear input topics and outputs. Reading order: `planner`, `sourcing`, `compliance`, `negotiation`, `critic`, `reporter`, `escalation`.
- `src/services/*.py`: mocks representing production microservices. Understand their APIs before adding new agents.
- `src/infrastructure/*.py`: distributed systems primitives (event bus, workflow state machine, idempotency). These simulate Kafka/Temporal behavior without external dependencies.
- `src/knowledge.py` & `src/retrieval/*`: retrieval logic. Study this when building new RAG features.
- `src/pipelines/*`: change data capture (CDC) and retrieval evaluation stubs.
- `demo.py`: CLI entrypoint orchestrating everything; useful for tracing runtime.

---

## 5. Running the Demo

Prerequisite: Python 3.11+

```bash
cd CPG
python demo.py --verbose
```

What you should see:
- Final recommendation JSON (supplier, compliance flags, KPIs).
- Workflow state summary (which tasks succeeded).
- Retrieval evaluator score (simple accuracy metric for RAG).
- Optional: Agent conversation log & sent emails when `--verbose` is used.

Understanding the output helps connect the high-level architecture to runtime behavior.

---

## 6. Service Layer Deep Dive

Understanding services is crucial because agents call them via tool interfaces.

### POService (`src/services/po_service.py`)
- Stores purchase orders (currently in-memory).
- `register_po` mimics registering a new PO via ERP ingestion.
- Typical production responsibilities: data validation, integration with SAP/Coupa, event emission (`po.created`).

### SupplierService (`src/services/supplier_service.py`)
- Maintains supplier catalog. `search_suppliers` filters by category/region/certification/diversity.
- Emits CDC events when suppliers are added/updated – our RAG uses these to stay fresh (`upsert_supplier`).
- In production: use Postgres + caching + risk models.

### ComplianceService (`src/services/compliance_service.py`)
- Evaluates deterministic policies (spend thresholds, required certifications, probation status).
- Returns `ComplianceResult` with issues list.
- Real implementation would call OPA/Drools or internal compliance API.

### AnalyticsService (`src/services/analytics_service.py`)
- Computes KPIs (estimated savings, diversity count) – scaffolding for the eventual analytics pipeline.

### MessagingService (`src/services/messaging_service.py`)
- Captures outbound email events. Replace with SES/SendGrid integration in production.

When extending the system, ensure new agents interact with services rather than mutating state themselves.

## 7. Agent Layer Deep Dive

Below we dissect each agent class and design rationale.

### Agent Base (`src/agents/base.py`)
- Defines `AgentContext` (per-PO shared state & conversation log) and `Agent` protocol (requires `input_topics` and `handle_event`).
- Agents remain stateless; any persistent info goes through services or context.

### PlannerAgent
- Input topic: `po.created`.
- Responsibilities: fetch PO from `POService`; query RAG for similar histories; create workflow skeleton via `WorkflowEngine`; publish `task.plan.completed`.
- Why: ensures downstream agents know task ordering; records policy references early.

### SourcingScoutAgent
- Uses `SupplierService` for authoritative supplier data, not RAG, to avoid stale info.
- Uses `HybridRetriever` for justification text. This is key for explainability.
- Publishes `supplier.shortlist.created`.

### ComplianceSentinelAgent
- Calls compliance engine and attaches policy citations via RAG.
- On failure emits `compliance.failed`, which `EscalationAgent` logs for human review.

### NegotiatorAgent
- Starts after compliance approval; uses RAG negotiation snippets.
- Guardrails validate email content before sending.
- Publishes `negotiation.round.completed` so Critic can assess.

### CriticAgent
- Safety net: re-checks compliance after negotiations in case data changed or negotiations introduced risk.
- Publishes `negotiation.validated` or `negotiation.validation_failed`.

### InsightsReporterAgent
- Final aggregator; collects KPIs, negotiations, citations, writes `report.ready`.

### EscalationAgent
- Tracks any failures, enabling human-in-loop workflows.

All agents adhere to the same structure: respond to event → call services/RAG → publish new events → update workflow state.

## 8. Knowledge & Retrieval Pipeline

### Why Graph + Vector?
- Vectors retrieve semantically similar text chunks.
- Graph captures structured relationships: e.g., `PO -> supplier -> certifications`. Without graph edges we lose chain-of-thought decisions.

### Knowledge Base (`src/knowledge.py`)
- `add_document`, `similarity_search`: bag-of-words placeholder for embeddings.
- `add_relation`, `traverse`: simple adjacency list graph.
- `upsert_supplier`: invoked by CDC to keep RAG in sync with SupplierService.

### Adapters & Retriever
- `src/retrieval/adapters.py`: wraps `KnowledgeBase` to mimic vector/graph APIs.
- `src/retrieval/hybrid.py`: orchestrates combined retrieval and returns debug info & citations (critical for evaluations).

### CDC Pipeline (`src/pipelines/cdc.py`)
- Services emit `CDCEvent`; knowledge base consumes and updates indexes.
- In production: integrate Debezium or service-specific change notifications.

### Retrieval Evaluation (`src/pipelines/retrieval_eval.py`)
- Simple hit-rate metric for QA. Hook into CI/CD to detect retrieval regressions.

## 9. Eventing & Workflow Orchestration Details

### EventBus (`src/infrastructure/event_bus.py`)
- In-memory pub/sub; each handler returns optional follow-up events.
- Real counterpart: Kafka topics with schemas, consumer groups, retries.

### IdempotencyRegistry (`src/infrastructure/idempotency.py`)
- Guards against duplicate processing. Key format uses event/topic info.

### WorkflowEngine (`src/infrastructure/workflow.py`)
- Stores tasks per PO with state transitions. Agents invoke `_advance_workflow` to update states.
- Realistic expansion: use Temporal or Camunda for long-running orchestrations and human tasks.

### Guardrails (`src/infrastructure/guardrails.py`)
- Placeholder to demonstrate safety checks (PII filtering, tone enforcement). Extend with actual policies.

### Coordinator (`src/coordinator.py`)
- Binds everything.
- Registers CDC handler to keep knowledge fresh.
- Creates `HybridRetriever` and `RetrievalEvaluator` instances and exposes them for diagnostics.
- Maintains workflow transition map to update task status automatically.

## 10. Coding Standards, Testing Strategy & Observability

### Coding Guidelines
- Prefer dependency injection (pass services/retrievers into agents) to allow test doubles.
- Use descriptive event topics; include `po_id` and `round` in payloads.
- Keep agent logic small and composable; delegate heavy lifting to services or helper modules.

### Testing Strategy
- **Unit tests**: target services (e.g., compliance checks) and agents with mocked dependencies.
- **Integration tests**: simulate event flows using the in-memory event bus.
- **Retrieval QA**: extend `RetrievalEvaluator` queries per category/policy.
- **Chaos experiments**: simulate failed events, duplicate messages, or stale knowledge to ensure system recovers gracefully.

### Observability Hooks
- `demo.py` prints workflow state and retrieval hit-rate to illustrate how runbooks should capture diagnostics.
- Extend with structured logging (JSON) and link to tracing IDs when integrating with real observability stack.

## 11. Worked Example: Adding a New Agent

---

## 7. Eventing & Workflow Orchestration

- `EventBus`: in-memory publish/subscribe; real deployments would use Kafka or Redis Streams.
- `IdempotencyRegistry`: prevents duplicate processing (critical in distributed systems).
- `WorkflowEngine`: tracks task states (`pending`, `in_progress`, `completed`, `failed`).
- `Guardrails`: simple stub to enforce policy checks before sending emails; expand with real validation.

---

## 8. Coding Standards & Best Practices

1. **Immutable Events**: never mutate event payloads after publishing.
2. **Idempotency**: ensure every agent action can be retried safely.
3. **Context Logging**: attach `po_id` to logs and messages for traceability.
4. **Retrieval Grounding**: always document the source (citation) when using RAG outputs.
5. **Feature Flags**: when adding new capabilities, plan for toggles to control rollout.
6. **Testability**: prefer pure functions or straightforward dependencies so units can be tested without infrastructure.

---

## 9. Adding a New Feature (Worked Example)


### Scenario: Add a “Risk Analyst Agent” that reviews supplier risk post-negotiation.

Steps:
1. **Design**: Define events it listens to (e.g., `negotiation.validated`) and outputs (e.g., `risk.review.completed`). Update `design.md` if needed.
2. **Create Agent Class** (`src/agents/risk_analyst.py`):
   - Inherit from `Agent` protocol.
   - Implement `handle_event` to fetch supplier risk scores (via `SupplierService`) and produce an assessment.
3. **Update Orchestrator**:
   - Import and register the agent.
   - Add workflow transitions for new events if necessary.
4. **Extend Demo**:
   - Print risk review summary in `demo.py`.
5. **Test**:
   - Run `python demo.py --verbose` to confirm the new agent triggers.
   - Consider writing unit tests for the agent’s logic using mocks.

### Tips for Feature Development
- Check `design.md` for architectural invariants (e.g., only services mutate state; agents remain stateless workers).
- Follow existing patterns: each agent returns a list of `Event` objects; avoid side effects outside services.
- Keep new modules self-contained to simplify future refactors.
- Write tests before wiring into the full pipeline when feasible.

## 12. Advanced Topics & Research Directions

For PhD-level engineers interested in deeper exploration:
- **Negotiation Strategy Optimization**: experiment with reinforcement learning or bandit algorithms to pick offers. Integrate with simulators before live deployment.
- **Retrieval Diagnostics**: implement vector similarity drift detection, embedding TTL strategies, or adaptive chunking.
- **Multi-Agent Coordination**: explore LangGraph or PettingZoo concepts for parallel negotiations, agent bidding, or meta-agents that choose strategy per category.
- **Explainability**: attach SHAP-like attributions for compliance decisions, log natural-language rationales with citations.
- **Security**: research adversarial prompts, PII leakage prevention, and tenant-aware guardrails.

## 13. FAQs & Further Resources

---

## 10. FAQs & Further Resources

**Q: Where do I start if I’m new to RAG?**
- Read `knowledge.py`, `retrieval/hybrid.py`, and the RAG section in `design.md`.
- Experiment with the `RetrievalEvaluator` to see how query quality affects results.

**Q: How do I debug agent flows?**
- Use the verbose demo to inspect conversation logs and workflow states.
- Insert temporary `print` statements or use logging with `po_id` to trace execution.

**Q: What about production dependencies?**
- Replace stubs with real services (Kafka, Temporal, Pinecone, Neo4j) incrementally.
- Coordinate with platform engineering for infrastructure provisioning, secrets management, and SRE runbooks.

**Recommended Reading:**
- Internal Confluence pages on Microservice Standards and AI Governance.
- “Designing Event-Driven Systems” (O’Reilly) for Kafka-style workflows.
- LangChain documentation on multi-agent orchestration.

---

## Next Steps for New Hires
1. Run the demo and trace agents + workflow state.
2. Read `design.md` end-to-end; note any questions.
3. Pick a small enhancement (e.g., add logging to an agent, extend retrieval evaluation) and submit a PR.
4. Schedule a mentorship session to review code and architecture.

Welcome aboard! With this guide, you should be able to navigate the codebase, understand the hybrid architecture, and start contributing meaningful improvements.
