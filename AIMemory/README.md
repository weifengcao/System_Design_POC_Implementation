# AIMemory: Long-Term Memory Layer for LLMs

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-beta-orange)

**AIMemory** is a standalone, open-source memory layer designed to give Large Language Models (LLMs) long-term persistence and semantic context. It bridges the gap between stateless LLM sessions and the need for continuous learning and personalization.

## 🚀 Features

- **Semantic Search**: Efficiently retrieve relevant past interactions using vector embeddings (ChromaDB).
- **Metadata Storage**: Store structured session data alongside unstructured text (SQLite).
- **Privacy First**: Built-in PII redaction middleware to protect sensitive user data.
- **Easy Integration**: Simple REST API built with FastAPI.
- **Local & Open**: Designed to run locally with open-source models, no external API keys required by default.

## 🛠️ Architecture

AIMemory consists of three main components:
1.  **API Gateway**: FastAPI-based REST interface.
2.  **Memory Controller**: Orchestrates embedding generation and storage.
3.  **Storage Layer**: Hybrid storage using ChromaDB (Vectors) and SQLite (Metadata).

## 📦 Installation

### Prerequisites
- Python 3.10+
- Docker (Optional)

### Local Setup

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/AIMemory.git
    cd AIMemory
    ```

2.  **Install Dependencies**
    ```bash
    pip install poetry
    poetry install
    # OR
    pip install -r requirements.txt
    ```

3.  **Run the Server**
    ```bash
    uvicorn main:app --reload
    ```

## ⚙️ Configuration

Configuration is managed via Environment Variables. You can create a `.env` file in the root directory:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `APP_NAME` | Name of the application | `LLM Memory Layer` |
| `DB_PATH` | Path to SQLite database | `aimemory.db` |
| `CHROMA_PATH` | Path to ChromaDB storage | `./chroma_db` |
| `EMBEDDING_MODEL` | SentenceTransformer model name | `all-MiniLM-L6-v2` |
| `ENABLE_PII_REDACTION` | Enable/Disable PII scrubbing | `True` |

## 📖 Usage

### Add a Memory
```bash
curl -X POST "http://localhost:8000/api/v1/memory" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "My favorite color is blue",
           "session_id": "session_123",
           "user_id": "user_abc"
         }'
```

### Search Memories
```bash
curl -X POST "http://localhost:8000/api/v1/memory/search" \
     -H "Content-Type: application/json" \
     -d '{
           "query": "What do I like?",
           "session_id": "session_123"
         }'
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
