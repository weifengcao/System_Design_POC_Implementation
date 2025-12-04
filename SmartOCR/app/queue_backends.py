from __future__ import annotations

from typing import Optional

from . import queue


class QueueBackend:
    def enqueue(self, job_id: str) -> None:
        raise NotImplementedError

    def pop(self) -> Optional[str]:
        raise NotImplementedError


class InMemoryQueueBackend(QueueBackend):
    def __init__(self) -> None:
        self.q = queue.InMemoryQueue()

    def enqueue(self, job_id: str) -> None:
        self.q.enqueue(job_id)

    def pop(self) -> Optional[str]:
        return self.q.pop()
