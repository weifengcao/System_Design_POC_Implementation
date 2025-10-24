from __future__ import annotations

from typing import Iterable

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..infrastructure.guardrails import enforce_guardrails, should_escalate


class ConversationAgent(Agent):
    input_topics: Iterable[str] = ("knowledge.retrieved", "user.message")

    def handle(self, event: Event, context: AgentContext):
        user_text = event.payload.get("text")
        if user_text:
            context.add_message("Customer", user_text)

        snippet = event.payload.get("snippet") or context.shared_state.get("last_snippet", "")
        base_response = snippet or "I'm here to help. Could you please provide more details?"
        response = enforce_guardrails(base_response)
        context.add_message("AI", response)

        metadata = {"sentiment": event.payload.get("sentiment"), "policy": None}
        if should_escalate(metadata):
            return [
                Event(
                    topic="conversation.escalate",
                    payload={"conversation_id": context.conversation_id, "reason": "negative sentiment"},
                )
            ]

        return [
            Event(
                topic="conversation.respond",
                payload={"conversation_id": context.conversation_id, "text": response},
            )
        ]
