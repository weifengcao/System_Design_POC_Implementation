from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class CDCEvent:
    entity: str
    entity_id: str
    operation: str
    payload: Dict[str, object]


class CDCIngestionPipeline:
    """Mock CDC pipeline streaming service updates into the knowledge base."""

    def __init__(self) -> None:
        self.subscribers: List = []

    def register(self, handler) -> None:
        self.subscribers.append(handler)

    def emit(self, event: CDCEvent) -> None:
        for handler in self.subscribers:
            handler(event)

