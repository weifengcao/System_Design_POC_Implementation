from __future__ import annotations

from typing import Iterable

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..infrastructure.workflow import TaskState, WorkflowEngine


TASKS = ["greeting", "auth", "resolution"]


class PlannerAgent(Agent):
    input_topics: Iterable[str] = ("conversation.started",)

    def __init__(self, workflow_engine: WorkflowEngine) -> None:
        self.workflow_engine = workflow_engine

    def handle(self, event: Event, context: AgentContext):
        self.workflow_engine.create(context.conversation_id, TASKS)
        context.shared_state["plan"] = TASKS
        return [
            Event(
                topic="planner.ready",
                payload={"conversation_id": context.conversation_id, "tasks": TASKS},
            )
        ]

