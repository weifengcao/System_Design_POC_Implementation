from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from .models import Video, VideoStatus


class VideoStore:
    """Simple in-memory store to back the MVP services."""

    def __init__(self) -> None:
        self._videos: Dict[UUID, Video] = {}
        self._lock = asyncio.Lock()

    async def add_video(self, video: Video) -> Video:
        async with self._lock:
            self._videos[video.video_id] = video
        return video

    async def list_videos(self) -> List[Video]:
        async with self._lock:
            return list(self._videos.values())

    async def get_video(self, video_id: UUID) -> Optional[Video]:
        async with self._lock:
            return self._videos.get(video_id)

    async def update_status(
        self,
        video_id: UUID,
        status: VideoStatus,
        manifest_url: Optional[str] = None,
    ) -> Optional[Video]:
        async with self._lock:
            video = self._videos.get(video_id)
            if not video:
                return None
            video.status = status
            if manifest_url:
                video.manifest_url = manifest_url
            video.updated_at = datetime.now(timezone.utc)
            return video

    async def increment_like(self, video_id: UUID) -> Optional[Video]:
        async with self._lock:
            video = self._videos.get(video_id)
            if not video:
                return None
            video.likes += 1
            video.updated_at = datetime.now(timezone.utc)
            return video

    async def record_view(
        self,
        video_id: UUID,
        watch_seconds: int,
    ) -> Optional[Video]:
        async with self._lock:
            video = self._videos.get(video_id)
            if not video:
                return None
            video.views += 1
            video.watch_seconds += watch_seconds
            video.updated_at = datetime.now(timezone.utc)
            return video

    async def top_videos(self, limit: int = 10) -> Iterable[Video]:
        videos = await self.list_videos()
        videos.sort(key=lambda v: (v.likes, v.views, v.created_at), reverse=True)
        return videos[:limit]
