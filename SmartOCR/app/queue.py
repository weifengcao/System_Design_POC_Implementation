from __future__ import annotations

from typing import Optional, List


class InMemoryQueue:
    """
    Simple FIFO queue abstraction to mirror the PRD's orchestrator/worker split.
    Swap this with SQS/Kafka/Redis for production.
    """

    def __init__(self) -> None:
        self._queue: List[str] = []

    def enqueue(self, job_id: str) -> None:
        self._queue.append(job_id)

    def pop(self) -> Optional[str]:
        if not self._queue:
            return None
        return self._queue.pop(0)
