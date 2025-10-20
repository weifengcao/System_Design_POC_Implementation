# YouTube MVP Prototype

This directory contains a minimal FastAPI-based prototype that demonstrates the core flows described in the system design document:

- Upload a video (metadata only) and trigger an asynchronous transcoding simulation.
- Fetch video metadata and playback a ready video.
- Interact with basic engagement actions (likes, views).
- Retrieve a simple personalized feed (top liked videos).

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r Youtube/requirements.txt
uvicorn Youtube.app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Visit `/docs` for interactive Swagger documentation.

## Sample Workflow

1. `POST /videos` with title/tags to enqueue a new upload.
2. Wait a couple of seconds for the background transcoder to mark it `READY`.
3. `GET /videos/{id}/play` to receive a mock manifest URL.
4. `POST /videos/{id}/like` and `GET /feed/home` to observe feed ordering.

The in-memory store keeps data for the life of the process only; this prototype is intended for local experimentation and interview demos.
