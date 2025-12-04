from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List

from . import models


@dataclass
class InMemoryDoc:
    id: str
    source_uri: str
    content: Optional[bytes] = None
    doc_type: str = "generic"


@dataclass
class Job:
    id: str
    external_id: Optional[str]
    source_uri: str
    status: str
    doc_type: str = "generic"
    webhook_url: Optional[str] = None
    result: Optional[models.OCRResult] = None
    error: Optional[str] = None
    tenant_id: Optional[str] = None


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._docs: Dict[str, InMemoryDoc] = {}

    def save(self, doc: InMemoryDoc) -> None:
        self._docs[doc.id] = doc

    def get(self, doc_id: str) -> Optional[InMemoryDoc]:
        return self._docs.get(doc_id)


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def save(self, job: Job) -> None:
        self._jobs[job.id] = job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self, limit: int = 50) -> List[Job]:
        return list(self._jobs.values())[:limit]

    def mark_in_progress(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.status = "in_progress"

    def complete(self, job_id: str, result: models.OCRResult) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.status = "completed"
            job.result = result

    def fail(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.status = "failed"
            job.error = error
