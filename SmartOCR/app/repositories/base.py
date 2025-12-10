from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List

from .. import models, storage


class JobRepository(ABC):
    """
    Repository abstraction for jobs; can be backed by Postgres or in-memory.
    """

    @abstractmethod
    def create(self, job: storage.Job) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, job_id: str) -> Optional[storage.Job]:
        raise NotImplementedError

    @abstractmethod
    def list(self, limit: int = 50) -> List[storage.Job]:
        raise NotImplementedError

    @abstractmethod
    def mark_in_progress(self, job_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def complete(self, job_id: str, result: models.OCRResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def fail(self, job_id: str, error: str) -> None:
        raise NotImplementedError
