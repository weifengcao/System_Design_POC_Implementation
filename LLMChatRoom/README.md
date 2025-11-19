# LLMChatroom POC

This proof-of-concept demonstrates the core ideas behind a collaborative chatroom where humans interact with each other and with an LLM assistant. The latest iteration adds persistence, a streaming-like LLM adapter, a FastAPI layer, and richer moderation/audit hooks.

## What's Included
- **Design doc:** `design.md` outlines architecture, data flows, and security measures.
- **Service prototype:** `poc.py` implements users, rooms, ACLs, chat history, rolling memory summaries, enhanced moderation + audit, JSON-based persistence, and a streaming LLM simulator.
- **FastAPI server:** `api.py` wires the service into HTTP endpoints (register users, rooms, send messages, query audit log).

## Running the Demo
```bash
cd LLMChatRoom
python poc.py         # CLI demo
pip install fastapi uvicorn  # one-time, if not already present
uvicorn api:app       # REST API
```

The CLI script creates a secure room, exchanges several messages, invokes the agent (`@Orion`), prints chat history, displays the rolling memory summary, attempts a blocked message from an unauthorized user, and dumps the audit tail. The API shares the same persistence so CLI/API interactions stay consistent.

## Next Steps Ideas
1. Swap the simulator with real LLM provider adapters + streaming token delivery downstream.
2. Replace JSON persistence with durable storage (Postgres/Redis/vector DB) and add WebSocket fan-out.
3. Integrate mature moderation/compliance tooling (PII classifiers, DLP policies, SOC2-grade audit sinks).
