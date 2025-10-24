# AICallCenter MVP

This minimum viable product implements a simplified version of the architecture outlined in `design.md`. It demonstrates how an AI-driven contact center can orchestrate conversations, retrieve knowledge, enforce guardrails, and collect analytics—all without real telephony infrastructure.

## Project Layout

```
AICallCenter/
├── data/knowledge/            # Sample FAQ, policies, scripted responses
├── src/
│   ├── agents/                # Planner, Retriever, Conversation, Escalation, Analytics
│   ├── infrastructure/        # Event bus, workflow engine, guardrails, idempotency
│   ├── services/              # Knowledge base, CRM stub, ticketing, analytics
│   ├── retrieval/             # Hybrid retriever wrapper
│   ├── orchestrator.py        # Wires agents, services, and events
│   └── demo_runner.py         # CLI entrypoint for interactive run
└── design.md                  # Full production design
```

## Running the Demo

```bash
cd AICallCenter
python -m src.demo_runner
```

Example output:

```
Customer: Hi, I want to check the status of my order 12345.
AI: Sure, let me look up order 12345. It is scheduled to arrive on Friday. I'll send you the tracking link.
Customer: Also, I was double charged on my credit card.
AI: I'm checking your billing history now. I see two charges on your credit card; I'll refund the duplicate within 3-5 business days.

Transcript:
...
```

The script simulates a single conversation, showing how user messages trigger knowledge retrieval, guardrail enforcement, and analytics logging.

## Extending the MVP
- Replace the keyword knowledge base with a vector database (FAISS/Pinecone) and add embeddings.
- Integrate real NLP sentiment analysis and ASR/TTS pipelines.
- Connect the tool executor to actual CRM/ticketing APIs.
- Add supervisor dashboard and human takeover logic.
- Instrument metrics via Prometheus/OpenTelemetry.

This code serves as a sandbox for experimenting with the hybrid microservice + agentic approach before scaling to the production design.

