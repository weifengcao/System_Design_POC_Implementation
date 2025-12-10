from __future__ import annotations

from typing import Optional, List

from .base import JobRepository
from .. import storage, models


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
