from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from Youtube.app.main import app


async def main() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/videos",
            json={
                "title": "Demo upload",
                "description": "Testing the MVP",
                "tags": ["demo", "upload"],
            },
        )
        response.raise_for_status()
        video_id = response.json()["video_id"]
        print(f"Uploaded video {video_id}, awaiting processing...")

        # Wait for background transcoding to complete.
        await asyncio.sleep(2)

        playback = client.get(f"/videos/{video_id}/play")
        print("Playback response:", playback.json())

        like = client.post(f"/videos/{video_id}/like")
        print("Like response:", like.json())

        feed = client.get("/feed/home")
        print("Home feed:", feed.json())


if __name__ == "__main__":
    asyncio.run(main())
