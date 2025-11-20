# LLM Memory Layer System Design

## 1. Problem Statement
Current LLMs are stateless. They lose context once a session ends or the context window is exceeded. This limits their ability to learn from past interactions, personalize responses, and maintain long-running tasks.

## 2. Objectives
- **Persistence**: Store chat history and derived facts across sessions.
- **Retrieval**: Efficiently retrieve relevant context based on the current query.
- **Latency**: Retrieval latency < 200ms.
- **Privacy**: Ensure user data isolation and optional PII redaction.
- **Open Source**: Build with open-source friendly components.

## 3. System Architecture

### High-Level Components
1.  **API Gateway (FastAPI)**: Async REST Interface. Accepts requests, validates auth, and enqueues tasks.
2.  **Message Queue (Redis)**: Buffers write requests for asynchronous processing. Secured with password.
3.  **Worker Service (Celery)**: Consumes tasks from Redis, generates embeddings, and writes to storage.
4.  **Embedding Service**: Runs inside the Worker. Converts text to vectors (e.g., SentenceTransformers).
5.  **Vector Store (ChromaDB)**: Server mode. Stores semantic embeddings. Network isolated.
6.  **Metadata Store (PostgreSQL)**: Stores structured data. Network isolated.

### Architecture Diagram
```mermaid
graph TD
    Client[Client App] -->|HTTPS + API Key| API[API Gateway]
    
    subgraph "Secure Internal Network"
        API -->|Enqueue Task| Redis[(Redis Queue)]
        Worker[Celery Worker] -->|Consume Task| Redis
        
        Worker -->|Read/Write| Postgres[(PostgreSQL)]
        Worker -->|Read/Write| Chroma[(ChromaDB)]
        
        API -->|Read (Search)| Chroma
        API -->|Read (History)| Postgres
    end
    
    style Client fill:#f9f,stroke:#333,stroke-width:2px
    style API fill:#bbf,stroke:#333,stroke-width:2px
    style Worker fill:#bfb,stroke:#333,stroke-width:2px
```

### Data Flow
1.  **Write Path (`/add`) - Async**:
    - Client sends `text`, `session_id`, optional `id`.
    - API validates Key, pushes task to Redis, returns `task_id`.
    - Worker picks up task:
        - Scrubs PII.
        - Generates embedding.
        - **Upserts** into ChromaDB (Idempotent).
        - **Upserts** into PostgreSQL (Idempotent).
2.  **Read Path (`/retrieve`)**:
    - Client sends `query`.
    - API computes query embedding (or delegates to search service).
    - Queries ChromaDB for top-k.
    - Enriches with metadata from Postgres.

## 4. Data Model

### Memory Object
```json
{
  "id": "uuid (or client provided)",
  "session_id": "string",
  "user_id": "string",
  "text": "string",
  "embedding": [float],
  "created_at": "timestamp",
  "metadata": {}
}
```

## 5. Security & Privacy (Zero Trust)
- **Authentication**: API Key required for all endpoints (`X-API-Key`).
- **Network Isolation**: DB, Redis, and Chroma are in a private Docker network, not exposed to host.
- **Secret Management**: Passwords/Keys loaded via Docker Secrets (`/run/secrets/`).
- **PII Redaction**: Automated scrubbing of sensitive data.
- **Encryption**: SSL enforced for Database connections.

## 6. Technology Stack
- **Language**: Python 3.10+
- **API**: FastAPI (Async)
- **Queue**: Redis 7 (Password Protected)
- **Worker**: Celery
- **Vector DB**: ChromaDB (Server Mode)
- **Database**: PostgreSQL 15 (Async + SSL)
- **Infrastructure**: Docker Compose, Docker Secrets

## 7. API Specification
- `POST /memory`: Add a new memory (Async, Idempotent).
- `POST /memory/search`: Semantic search.
- `GET /sessions/{id}/history`: Get full history.

