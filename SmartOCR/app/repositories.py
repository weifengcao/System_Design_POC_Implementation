from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from . import models, storage


@dataclass
class JobRecord:
    id: str
    external_id: Optional[str]
    source_uri: str
    status: str
    doc_type: str
    webhook_url: Optional[str]
    result: Optional[models.OCRResult]
    error: Optional[str]


class JobRepository:
    """
    Repository abstraction for jobs; can be backed by Postgres or in-memory.
    """

    def create(self, job: storage.Job) -> None:
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[storage.Job]:
        raise NotImplementedError

    def list(self, limit: int = 50) -> List[storage.Job]:
        raise NotImplementedError

    def mark_in_progress(self, job_id: str) -> None:
        raise NotImplementedError

    def complete(self, job_id: str, result: models.OCRResult) -> None:
        raise NotImplementedError

    def fail(self, job_id: str, error: str) -> None:
        raise NotImplementedError


class InMemoryJobRepository(JobRepository):
    def __init__(self) -> None:
        self.store = storage.InMemoryJobStore()

    def create(self, job: storage.Job) -> None:
        self.store.save(job)

    def get(self, job_id: str) -> Optional[storage.Job]:
        return self.store.get(job_id)

    def list(self, limit: int = 50) -> List[storage.Job]:
        return self.store.list(limit=limit)

    def mark_in_progress(self, job_id: str) -> None:
        self.store.mark_in_progress(job_id)

    def complete(self, job_id: str, result: models.OCRResult) -> None:
        self.store.complete(job_id, result)

    def fail(self, job_id: str, error: str) -> None:
        self.store.fail(job_id, error)
