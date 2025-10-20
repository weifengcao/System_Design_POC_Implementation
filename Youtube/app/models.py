from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4


class VideoStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass
class Video:
    title: str
    description: Optional[str]
    tags: List[str]
    channel_id: UUID
    video_id: UUID = field(default_factory=uuid4)
    status: VideoStatus = VideoStatus.UPLOADED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    manifest_url: Optional[str] = None
    likes: int = 0
    views: int = 0
    watch_seconds: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "video_id": str(self.video_id),
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "channel_id": str(self.channel_id),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "manifest_url": self.manifest_url,
            "likes": self.likes,
            "views": self.views,
            "watch_seconds": self.watch_seconds,
        }
