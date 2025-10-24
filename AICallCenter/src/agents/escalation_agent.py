from __future__ import annotations

from typing import Iterable

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event


class EscalationAgent(Agent):
    input_topics: Iterable[str] = ("conversation.escalate",)

    def handle(self, event: Event, context: AgentContext):
        context.shared_state["escalated"] = True
        return [
            Event(
                topic="conversation.respond",
                payload={"conversation_id": context.conversation_id, "text": "I'm transferring you to a specialist now."},
            )
        ]

