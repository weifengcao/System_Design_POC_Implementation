from __future__ import annotations

from pathlib import Path
from typing import Dict

from .agents.analytics_agent import AnalyticsAgent
from .agents.conversation_agent import ConversationAgent
from .agents.escalation_agent import EscalationAgent
from .agents.planner import PlannerAgent
from .agents.retriever_agent import RetrieverAgent
from .agents.base import AgentContext
from .infrastructure.event_bus import Event, EventBus
from .infrastructure.idempotency import IdempotencyTracker
from .infrastructure.workflow import WorkflowEngine
from .retrieval.hybrid import HybridRetriever
from .services.analytics import AnalyticsService
from .services.knowledge import KnowledgeBase, load_default_knowledge


class Orchestrator:
    def __init__(self, knowledge_base: KnowledgeBase, analytics_service: AnalyticsService) -> None:
        self.event_bus = EventBus()
        self.idempotency = IdempotencyTracker()
        self.workflow_engine = WorkflowEngine()
        self.contexts: Dict[str, AgentContext] = {}

        retriever = HybridRetriever(knowledge_base)

        self.agents = [
            PlannerAgent(self.workflow_engine),
            RetrieverAgent(retriever),
            ConversationAgent(),
            EscalationAgent(),
            AnalyticsAgent(analytics_service),
        ]

        for agent in self.agents:
            for topic in agent.input_topics:
                self.event_bus.subscribe(topic, self._wrap(agent))

    def _wrap(self, agent):
        def handler(event: Event):
            cid = event.payload["conversation_id"]
            context = self.contexts.setdefault(cid, AgentContext(conversation_id=cid))
            key = event.idempotency_key or f"{event.event_id}:{agent.__class__.__name__}"
            if not self.idempotency.check(key, agent.__class__.__name__):
                return []
            return agent.handle(event, context)

        return handler

    def start_conversation(self, conversation_id: str) -> AgentContext:
        event = Event(topic="conversation.started", payload={"conversation_id": conversation_id})
        self.event_bus.publish(event)
        return self.contexts[conversation_id]

    def send_user_message(self, conversation_id: str, text: str, sentiment: float = 0.0) -> str:
        self.event_bus.publish(
            Event(
                topic="user.message",
                payload={"conversation_id": conversation_id, "text": text, "sentiment": sentiment},
            )
        )
        response_event = Event(topic="dummy", payload={})
        context = self.contexts[conversation_id]
        for message in reversed(context.transcript):
            if message.startswith("AI:"):
                return message.replace("AI: ", "")
        return ""

    def end_conversation(self, conversation_id: str, sentiment: float) -> None:
        self.event_bus.publish(
            Event(
                topic="conversation.ended",
                payload={"conversation_id": conversation_id, "sentiment": sentiment},
            )
        )


def build_orchestrator(base_path: Path) -> Orchestrator:
    kb = load_default_knowledge(base_path / "data" / "knowledge")
    analytics_service = AnalyticsService()
    return Orchestrator(kb, analytics_service)
