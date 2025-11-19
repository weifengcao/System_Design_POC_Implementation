# LLMChatroom – Design POC

## Goals
- Enable collaborative chatrooms where humans can talk with each other and with LLM agents.
- Persist chat history with searchable context and configurable retention.
- Provide lightweight memory so the agent responds with awareness of room context.
- Enforce security: authenticated users, role-based room membership, logging, and guardrails for the LLM agent.
- Deliver a working POC that demonstrates the main flows without external dependencies.

## Functional Requirements
1. Users can create/join chatrooms, send text messages, and see chronological history.
2. Each room can optionally include one or more LLM agents (e.g., “ChatGPT”) that auto-respond when mentioned or on every message.
3. Chat history is retained, with pagination and summarization to keep context manageable.
4. Support private/public rooms with access control lists.
5. Provide moderation hooks: redaction, toxicity checks, configurable message visibility.
6. System exposes APIs (or events) so clients (web/mobile) can subscribe to room updates.

## Non-Functional Requirements
- **Scalability:** thousands of concurrent rooms, millions of messages/day. Event-driven architecture to scale horizontally.
- **Latency:** human-like response times (<500ms for history, <2s for LLM replies).
- **Reliability:** no single point of failure; data durability through replicated storage.
- **Security & Privacy:** encrypted transport, at-rest encryption, strict RBAC, audit logging.
- **Observability:** metrics on message throughput, agent latency, moderation outcomes.

## High-Level Architecture
```
Client Apps ─┬─> API Gateway ──> Chat Service ──┬─> Message Store (NoSQL / log)
             │                                  ├─> Presence Service
             │                                  ├─> Memory Service (vector DB + summaries)
             │                                  └─> Event Bus (Kafka / Redis streams)
             └─> WebSocket Gateway <─────────────┘

LLM Worker Fleet <──> Prompt Orchestrator <──> Memory Service + Policy Engine
```
- **API Gateway:** AuthN/Z, throttling, SSL termination.
- **Chat Service:** CRUD for rooms, membership management, message persistence, emits events for real-time fan-out.
- **WebSocket Gateway:** Push updates to connected clients, handles presence heartbeat.
- **Message Store:** Append-only log (e.g., DynamoDB + S3) with TTL policies.
- **Memory Service:** Maintains rolling summaries & embeddings per room; reconstructs context for LLM prompts.
- **Prompt Orchestrator:** Applies policies, injects system prompts, requests completions from selected LLM backends, handles retries & streaming output.
- **Policy/Guardrails:** Checks for data loss prevention (PII), toxicity, jailbreak patterns; can redact or block messages.
- **Observability:** Traces through OpenTelemetry, metrics per component. Audit logs stored immutably.

## Data Model (simplified)
- `User`: `{user_id, name, hashed_auth, roles}`
- `Room`: `{room_id, name, type(public/private), members[], agent_configs[], retention_policy}`
- `Message`: `{message_id, room_id, sender_id, body, mentions[], created_at, moderation_state, visible_to[]}`
- `Summary`: `{room_id, window_id, text, embedding, created_at}`
- `MemoryPointer`: `{room_id, message_id, vector_id}` for quick retrieval.

## Message Flow (with LLM agent)
1. User sends message via WebSocket/API.
2. Chat Service validates ACL, writes to log, publishes `message.created` event.
3. Moderation pipeline inspects content asynchronously; can redact or quarantine.
4. Memory Service updates rolling summary + embeddings for retrieval.
5. If message triggers agent (mention or always-on), Prompt Orchestrator fetches relevant history (last N messages + summary + retrieved vectors) and calls LLM backend.
6. Agent response stored as another message/event, delivered to clients.
7. Audit logs capture prompt+response metadata (but redact user PII).

## Security Considerations
- OAuth2 / enterprise SSO for authentication.
- Room-level RBAC (owner, moderator, member, guest) enforced for send/read permissions.
- Encryption in-transit (TLS) and at-rest (KMS-managed keys).
- Rate limiting per user/room; anomaly detection for spam/bot activity.
- Guardrails on LLM prompts (PII stripping, jailbreak filters) and responses (toxicity, hallucination detection).
- Audit + compliance logging with tamper-proof storage.

## POC Scope
- In-memory chat service with multiple rooms, simple ACL, and mock users.
- Deterministic “LLM” agent that uses room history + summary to craft replies (now updated to a streaming simulator + audit logging).
- Memory component keeps full history plus periodic summaries (e.g., every 5 messages).
- CLI demonstration script plus FastAPI layer: create rooms, send messages, attach agents, query history/audit.
- JSON persistence layer to snapshot state and mimic database durability.
- Security knobs represented via basic permissions, message redaction hooks, risk scoring, and auditable traces.

## Future Work
- Replace mock LLM with actual provider adapters and streaming output.
- Persist data in Postgres + Redis + vector DB.
- Implement full WebSocket gateway and offline delivery.
- Add moderation integrations (Perspective API, custom classifiers) and compliance exports.
