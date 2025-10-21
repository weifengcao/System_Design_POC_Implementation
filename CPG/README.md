# CPG Procurement Copilot (Agentic RAG Demo)

This repository implements the hybrid microservice + agentic architecture described in `design.md`. It couples deterministic “services” (PO intake, supplier registry, compliance engine, analytics, messaging) with LangChain-style agents, a graph-augmented RAG layer, and an event-driven orchestration fabric so you can explore how intelligent agents collaborate with traditional backends—all without external LLM APIs.

## Project Layout
- `data/knowledge/` – policies, supplier dossiers, and negotiation snippets ingested into the RAG fabric.
- `data/purchase_orders/` – sample purchase orders used to drive the workflow.
- `src/services/` – PO, supplier, compliance, analytics, and messaging “microservices” with simple in-memory stores/APIs.
- `src/knowledge.py` – lightweight vector + graph memory used for retrieval-augmented reasoning.
- `src/infrastructure/` – mock event bus, workflow engine, idempotency registry, and guardrail scaffolding representing Kafka/Temporal integrations.
- `src/retrieval/` – adapters and hybrid retriever shell used by agents when querying the knowledge fabric.
- `src/pipelines/` – CDC and retrieval evaluation stubs illustrating how services feed the RAG fabric.
- `docs/TRAINING_GUIDE.md` – onboarding playbook for new hires.
- `src/agents/` – planner, sourcing scout, compliance sentinel, negotiator, critic, and reporter agents that consume events and call both services and RAG.
- `src/coordinator.py` – event-driven orchestrator wiring services, agents, and infrastructure components.
- `demo.py` – CLI entrypoint producing a recommendation report and optional conversation trace.

## Running the Demo
```bash
cd CPG
python demo.py --verbose
```

Example output includes the recommended supplier, compliance flags, KPI summary, and drafted negotiation emails. Use the verbose flag to inspect the agent interaction log and outbound messages.

## Extending the Sandbox
- Replace the naive vector store with LangChain retrievers (FAISS, Chroma) and real embeddings pinned to service version metadata.
- Swap the scripted agents for LangChain RunnableSequences or LangGraph workflows that call live LLMs and true service APIs.
- Add new agents (risk analyst, finance reviewer) and tools (email gateways, pricing APIs, contract generators).
- Instrument token usage, retrieval quality metrics, guardrails, and Temporal checkpoints spanning both services and agents.

This codebase favors approachability so you can iterate quickly while exploring RAG + multi-agent design patterns.
