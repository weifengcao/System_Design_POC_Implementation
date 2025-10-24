from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict, Dict, Iterable, List, Optional
from collections import defaultdict


@dataclass(frozen=True)
class Event:
    topic: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: Optional[str] = None


EventHandler = Callable[[Event], Iterable[Event] | None]


class EventBus:
    """In-memory event bus for prototyping."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, event: Event) -> None:
        for handler in list(self._subscribers.get(event.topic, [])):
            follow_ups = handler(event)
            if follow_ups:
                for follow in follow_ups:
                    self.publish(follow)

