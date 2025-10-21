from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict, Dict, List, Optional
from collections import defaultdict


@dataclass(frozen=True)
class Event:
    topic: str
    payload: Dict[str, Any]
    idempotency_key: Optional[str] = None
    headers: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


EventHandler = Callable[[Event], Optional[List[Event]]]


class EventBus:
    """In-memory event bus placeholder for Kafka/Redis Streams semantics."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, event: Event) -> None:
        handlers = list(self._subscribers.get(event.topic, []))
        for handler in handlers:
            follow_up = handler(event)
            if follow_up:
                for follow in follow_up:
                    self.publish(follow)

