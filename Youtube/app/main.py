from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .models import Video, VideoStatus
from .storage import VideoStore
from .transcoder import TranscodeJob, TranscodeWorker

app = FastAPI(title="YouTube MVP API", version="0.1.0")
store = VideoStore()


class VideoUploadRequest(BaseModel):
    title: str = Field(..., example="My first vlog")
    description: str | None = Field(None, example="Behind the scenes of building an MVP.")
    tags: List[str] = Field(default_factory=list)
    channel_id: UUID | None = Field(None, description="Creator channel identifier")


class PlaybackResponse(BaseModel):
    manifest_url: str
    status: VideoStatus


async def notify_ready(video_id: UUID) -> None:
    video = await store.get_video(video_id)
    if video:
        print(f"[Notifier] Video {video.video_id} is ready with manifest {video.manifest_url}")


worker_with_notification = TranscodeWorker(store, notifier=notify_ready)


@app.post("/videos", status_code=202)
async def upload_video(request: VideoUploadRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    channel_id = request.channel_id or uuid4()
    video = Video(
        title=request.title,
        description=request.description,
        tags=request.tags,
        channel_id=channel_id,
    )
    await store.add_video(video)
    job = TranscodeJob(video.video_id)
    background_tasks.add_task(worker_with_notification.process, job)
    return {"video_id": str(video.video_id), "status": video.status}


@app.get("/videos")
async def list_videos() -> Dict[str, List[Dict[str, Any]]]:
    videos = await store.list_videos()
    return {"videos": [video.to_dict() for video in videos]}


@app.get("/videos/{video_id}")
async def get_video(video_id: UUID) -> Dict[str, Any]:
    video = await store.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video.to_dict()


@app.get("/videos/{video_id}/play", response_model=PlaybackResponse)
async def playback(video_id: UUID) -> PlaybackResponse:
    video = await store.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status != VideoStatus.READY:
        raise HTTPException(status_code=409, detail=f"Video state is {video.status}")
    await store.record_view(video.video_id, watch_seconds=60)
    return PlaybackResponse(manifest_url=video.manifest_url or "", status=video.status)


@app.post("/videos/{video_id}/like")
async def like(video_id: UUID) -> Dict[str, Any]:
    video = await store.increment_like(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"video_id": str(video.video_id), "likes": video.likes}


@app.get("/feed/home")
async def home_feed(limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    videos = await store.top_videos(limit)
    ready_videos = [video for video in videos if video.status == VideoStatus.READY]
    return {"videos": [video.to_dict() for video in ready_videos]}


# Convenience startup hook to demonstrate pre-populated data
@app.on_event("startup")
async def preload_sample_data() -> None:
    sample_titles = [
        "Scaling video transcoding pipelines",
        "SRE deep dive: incident response",
        "Understanding adaptive bitrate streaming",
    ]
    for title in sample_titles:
        video = Video(
            title=title,
            description=f"{title} tutorial",
            tags=["tech", "video"],
            channel_id=uuid4(),
        )
        await store.add_video(video)
        # Pretend these videos are already ready to serve.
        await store.update_status(
            video.video_id,
            VideoStatus.READY,
            manifest_url=f"https://cdn.example.com/videos/{video.video_id}/master.m3u8",
        )
        await store.record_view(video.video_id, watch_seconds=120)
