from __future__ import annotations

from typing import Iterable

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..services.analytics import AnalyticsService, ConversationMetrics


class AnalyticsAgent(Agent):
    input_topics: Iterable[str] = ("conversation.ended",)

    def __init__(self, analytics_service: AnalyticsService) -> None:
        self.analytics_service = analytics_service

    def handle(self, event: Event, context: AgentContext):
        sentiment = event.payload.get("sentiment", 0.0)
        escalated = bool(context.shared_state.get("escalated"))
        metrics = ConversationMetrics(conversation_id=context.conversation_id, sentiment=sentiment, escalated=escalated)
        self.analytics_service.record(metrics)
        return []

