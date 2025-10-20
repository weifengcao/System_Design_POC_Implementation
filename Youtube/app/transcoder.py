from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

from .models import VideoStatus
from .storage import VideoStore


@dataclass
class TranscodeJob:
    video_id: UUID
    target_representations: tuple[str, ...] = ("1080p", "720p", "480p")


class TranscodeWorker:
    """Extremely simplified transcoding worker that simulates processing time."""

    def __init__(
        self,
        store: VideoStore,
        delay_seconds: float = 1.5,
        notifier: Callable[[UUID], Awaitable[None]] | None = None,
    ) -> None:
        self._store = store
        self._delay_seconds = delay_seconds
        self._notifier = notifier

    async def process(self, job: TranscodeJob) -> None:
        await self._store.update_status(job.video_id, VideoStatus.PROCESSING)
        # Simulate time-consuming encoding work.
        await asyncio.sleep(self._delay_seconds)
        manifest_url = f"https://cdn.example.com/videos/{job.video_id}/master.m3u8"
        await self._store.update_status(job.video_id, VideoStatus.READY, manifest_url)
        if self._notifier:
            await self._notifier(job.video_id)
