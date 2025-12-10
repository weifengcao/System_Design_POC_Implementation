from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from . import queue


class QueueBackend(ABC):
    """
    Abstract base class for synchronous queue backends.
    """

    @abstractmethod
    def enqueue(self, job_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def pop(self) -> Optional[str]:
        raise NotImplementedError


class AsyncQueueBackend(ABC):
    """
    Abstract base class for asynchronous queue backends.
    """

    @abstractmethod
    async def enqueue(self, job_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def pop(self) -> Optional[str]:
        raise NotImplementedError


class InMemoryQueueBackend(QueueBackend):
    """
    A synchronous in-memory queue backend.
    """

    def __init__(self) -> None:
        self.q = queue.InMemoryQueue()

    def enqueue(self, job_id: str) -> None:
        self.q.enqueue(job_id)

    def pop(self) -> Optional[str]:
        return self.q.pop()


class AsyncInMemoryQueueBackend(AsyncQueueBackend):
    """
    An asynchronous in-memory queue backend.
    """

    def __init__(self) -> None:
        self.q = queue.InMemoryQueue()

    async def enqueue(self, job_id: str) -> None:
        self.q.enqueue(job_id)

    async def pop(self) -> Optional[str]:
        return self.q.pop()
