from __future__ import annotations

from typing import Iterable

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..retrieval.hybrid import HybridRetriever


class RetrieverAgent(Agent):
    input_topics: Iterable[str] = ("user.message",)

    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    def handle(self, event: Event, context: AgentContext):
        query = event.payload["text"]
        docs = self.retriever.retrieve(query).documents
        snippet = docs[0].content if docs else ""
        context.shared_state["last_snippet"] = snippet
        return [
            Event(
                topic="knowledge.retrieved",
                payload={"conversation_id": context.conversation_id, "snippet": snippet},
            )
        ]
