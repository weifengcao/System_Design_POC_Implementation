from __future__ import annotations

from typing import List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event


class EscalationAgent(Agent):
    name = "EscalationAgent"
    input_topics = ("compliance.failed", "negotiation.validation_failed")

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        escalations = context.shared_state.setdefault("escalations", [])
        escalations.append({"topic": event.topic, "payload": event.payload})
        context.add_message(
            self.name,
            f"Escalation recorded for {event.topic} with issues={event.payload.get('issues', [])}",
        )
        return [
            Event(
                topic="escalation.logged",
                payload={"po_id": event.payload["po_id"], "topic": event.topic},
                idempotency_key=f"{event.payload['po_id']}::escalation::{event.topic}",
            )
        ]
