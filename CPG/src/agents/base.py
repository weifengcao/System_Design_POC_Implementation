from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Protocol

from ..infrastructure.event_bus import Event


@dataclass
class AgentMessage:
    sender: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentContext:
    po_id: str
    conversation: List[AgentMessage] = field(default_factory=list)
    shared_state: Dict[str, object] = field(default_factory=dict)

    def add_message(self, sender: str, content: str, **metadata: str) -> None:
        self.conversation.append(AgentMessage(sender=sender, content=content, metadata=metadata))


class Agent(Protocol):
    name: str
    input_topics: Iterable[str]

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        ...

