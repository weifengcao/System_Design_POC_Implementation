from __future__ import annotations

import asyncio
import base64
import uuid
from typing import Optional
from urllib.parse import urlparse

import anyio
import httpx
from fastapi import HTTPException, status

from . import config, models, pipeline, storage, ingestion
from .repositories import JobRepository
from .queue_backends import AsyncQueueBackend


class Downloader:
    """
    Handles fetching content from URIs.
    """

    async def fetch_bytes(self, source_uri: str) -> bytes:
        parsed = urlparse(source_uri)
        if parsed.scheme == "data":
            if ";base64," in source_uri:
                b64 = source_uri.split(",")[1]
                return base64.b64decode(b64)
            return source_uri.split(",", 1)[1].encode()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(source_uri)
            resp.raise_for_status()
            return resp.content


from .object_store import MinioDocumentStore


class JobService:
    """
    Coordinates document storage, pipeline execution, and job lifecycle.
    """

    def __init__(
        self,
        docs: MinioDocumentStore,
        jobs: JobRepository,
        queue: AsyncQueueBackend,
        downloader: Downloader,
    ) -> None:
        self.docs = docs
        self.jobs = jobs
        self.queue = queue
        self.downloader = downloader

    async def create_job(
        self,
        *,
        source_uri: str,
        external_id: Optional[str],
        webhook_url: Optional[str],
        doc_type: str = "generic",
        tenant_id: Optional[str] = None,
    ) -> models.JobCreated:
        job_id = uuid.uuid4()
        content = await self.downloader.fetch_bytes(source_uri)
        doc_path = self.docs.save(str(job_id), content)

        job = storage.Job(
            id=job_id,
            external_id=external_id,
            source_uri=doc_path,
            status="queued",
            webhook_url=webhook_url,
            doc_type=doc_type,
            tenant_id=tenant_id,
        )
        self.jobs.create(job)
        await self.queue.enqueue(str(job_id))
        return models.JobCreated(job_id=str(job_id), status="queued", doc_type=doc_type)

    async def get_job(self, job_id: str) -> Optional[storage.Job]:
        return self.jobs.get(job_id)

    async def list_jobs(self, limit: int = 50) -> list[storage.Job]:
        return self.jobs.list(limit=limit)

    async def update_review(self, job_id: str, fields: list[models.FieldEntry]) -> models.JobStatus:
        job = self.jobs.get(job_id)
        if not job or not job.result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or not completed")
        job.result.fields = fields
        return models.JobStatus(job_id=job.id, status=job.status, result=job.result)

    async def worker(self, stop_event: asyncio.Event):
        """
        Continuously polls the queue for new jobs and processes them.
        """
        while not stop_event.is_set():
            try:
                await self.process_next_job()
                await anyio.sleep(0.1)  # Short sleep to prevent busy-waiting
            except Exception:
                # Log exceptions in a real app
                await anyio.sleep(5)  # Longer sleep on error

    async def process_next_job(self) -> None:
        job_id = await self.queue.pop()
        if not job_id:
            return
        self.jobs.mark_in_progress(job_id)
        job = self.jobs.get(job_id)
        if not job:
            return  # Should not happen if queue and DB are consistent

        try:
            content = self.docs.get(job.id)
            result = pipeline.run_ocr(content, doc_type=job.doc_type)
            result.job_id = job.id
            result.source_uri = job.source_uri
            self.jobs.complete(job.id, result)

            if job.webhook_url:
                await self._send_webhook(job.webhook_url, result)
        except Exception as exc:
            self.jobs.fail(job.id, error=str(exc))

    async def _send_webhook(self, url: str, result: models.OCRResult) -> None:
        timeout = config.settings.webhook_timeout_seconds
        max_attempts = 3
        backoff = 0.5
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = await client.post(url, json=result.model_dump())
                    if resp.is_success:
                        return
                except httpx.RequestError:
                    pass
                await anyio.sleep(backoff * attempt)
