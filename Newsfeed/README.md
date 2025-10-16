# Personal News Hub POC

![Personal News Hub UI](static/ui-screenshot.png)

This folder contains an end-to-end proof of concept for the newsfeed system described in `design.md`. It includes an in-memory backend service, seed data, a lightweight web UI, and support for multi-modal items such as articles, podcasts, and embedded video (YouTube).

## Features
- Personalized feed backed by topic interests, recency, source quality, and popularity heuristics.
- Breaking news fan-out with recent item buffer.
- Text-to-Speech simulation with cached assets and per-item playback.
- Topic management UI that lets you follow/unfollow topics per user.
- Sample embedded YouTube video to exercise video rendering.

## Project Structure
- `newsfeed_service.py` – Main HTTP service (feed, interests, TTS, breaking news, static assets).
- `static/index.html` – Single-page interface served by the backend.
- `static/ui-screenshot.png` – Generated preview of the web UI.
- `design.md` / `design.txt` – Original system design notes.

## Getting Started
```bash
cd Newsfeed
python newsfeed_service.py
```

The service starts on `http://127.0.0.1:8077/` and seeds demo users, interests, items, and a breaking news event.

### Sample Endpoints
- `GET /feed?user_id=1&lang=en` – Fetch the personalized feed.
- `GET /breaking` – Retrieve recent breaking news.
- `GET /topics` – List known topics derived from ingested content.
- `POST /interests` / `DELETE /interests` – Manage user-topic subscriptions.
- `GET /item/{id}/tts?lang=en` – Request a TTS asset for a given article.

## UI Walkthrough
1. Choose a demo user and language in the “Feed Controls” section.
2. Inspect the “Topics” section to toggle interests; the feed updates after each change.
3. Review the personalized feed, including:
   - Inline embedded video playback for the YouTube seed story.
   - TTS playback buttons for text/audio content.
   - Links out to original sources.
4. The Breaking News panel refreshes every 30 seconds to mimic ticker updates.

## Extending the POC
- Swap in persistent stores (Postgres, Redis) for the in-memory facsimiles.
- Plug the TTS endpoint into a real synthesis provider and CDN.
- Expand ingestion to repurpose real publisher feeds or a crawler pipeline.
- Add authentication and user management to move beyond demo accounts.

Feel free to iterate on the design and implementation. The modular structure should make it straightforward to drop in real dependencies or evolve the ranking logic.
