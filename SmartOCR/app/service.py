from __future__ import annotations

import base64
import uuid
from typing import Optional
from urllib.parse import urlparse

import anyio
import httpx
from fastapi import HTTPException, status

from . import config, models, pipeline, storage, ingestion
from .repositories import InMemoryJobRepository, JobRepository
from .queue_backends import InMemoryQueueBackend, QueueBackend


class JobService:
    """
    Coordinates document storage, pipeline execution, and job lifecycle.
    Abstracts queue/backend so API handlers stay thin.
    """

    def __init__(
        self,
        docs: storage.InMemoryDocumentStore,
        jobs: JobRepository,
        queue: QueueBackend,
    ) -> None:
        self.docs = docs
        self.jobs = jobs
        self.queue = queue

    async def fetch_bytes(self, source_uri: str) -> bytes:
        parsed = urlparse(source_uri)
        if parsed.scheme == "data":
            # Simple data URI handler: data:[<mediatype>][;base64],<data>
            if ";base64," in source_uri:
                b64 = source_uri.split(",")[1]
                return base64.b64decode(b64)
            return source_uri.split(",", 1)[1].encode()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(source_uri)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail="Failed to fetch source_url")
            return resp.content

    async def process_sync(self, *, file_bytes: bytes, source_uri: str, doc_type: str = "generic") -> models.OCRResult:
        doc_id = uuid.uuid4().hex
        doc = storage.InMemoryDoc(id=doc_id, source_uri=source_uri, content=file_bytes, doc_type=doc_type)
        self.docs.save(doc)
        result = pipeline.run_ocr(doc, doc_type=doc_type)
        return result

    async def create_job(
        self,
        *,
        source_uri: str,
        external_id: Optional[str],
        webhook_url: Optional[str],
        doc_type: str = "generic",
        tenant_id: Optional[str] = None,
    ) -> models.JobCreated:
        job_id = uuid.uuid4().hex
        job = storage.Job(
            id=job_id,
            external_id=external_id,
            source_uri=source_uri,
            status="queued",
            webhook_url=webhook_url,
            doc_type=doc_type,
            tenant_id=tenant_id,
        )
        self.jobs.create(job)
        self.queue.enqueue(job_id)
        return models.JobCreated(job_id=job_id, status="queued", doc_type=doc_type)

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

    async def process_next_job(self) -> None:
        job_id = self.queue.pop()
        if not job_id:
            return
        self.jobs.mark_in_progress(job_id)
        job = self.jobs.get(job_id)
        if not job:
            return
        doc = self.docs.get(job.id)
        if not doc:
            try:
                content = await self.fetch_bytes(job.source_uri)
            except Exception as exc:
                self.jobs.fail(job.id, error=str(exc))
                return
            doc = storage.InMemoryDoc(id=job.id, source_uri=job.source_uri, content=content, doc_type=job.doc_type)
            self.docs.save(doc)

        try:
            result = pipeline.run_ocr(doc, doc_type=job.doc_type)
            self.jobs.complete(job.id, result)
            if job.webhook_url:
                await self._send_webhook(job.webhook_url, result)
        except Exception as exc:  # pragma: no cover - failsafe
            self.jobs.fail(job.id, error=str(exc))

    async def _send_webhook(self, url: str, result: models.OCRResult) -> None:
        timeout = config.settings.webhook_timeout_seconds
        max_attempts = 3
        backoff = 0.5
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = await client.post(url, json=result.model_dump())
                    if resp.status_code < 400:
                        return
                except Exception:
                    pass
                await anyio.sleep(backoff * attempt)
