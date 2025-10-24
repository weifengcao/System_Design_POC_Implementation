from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Protocol

from ..infrastructure.event_bus import Event


@dataclass
class AgentContext:
    conversation_id: str
    shared_state: Dict[str, object] = field(default_factory=dict)
    transcript: List[str] = field(default_factory=list)

    def add_message(self, speaker: str, text: str) -> None:
        self.transcript.append(f"{speaker}: {text}")


class Agent(Protocol):
    input_topics: Iterable[str]

    def handle(self, event: Event, context: AgentContext) -> Iterable[Event] | None:
        ...

