from __future__ import annotations

from typing import List

from .base import BaseAgent
from ..config import TaskConfig


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="planner")

    def plan(self, task: TaskConfig) -> List[str]:
        steps = []
        if task.description:
            steps.append(task.description.strip())
        for command in task.commands:
            steps.append(f"Run command: {command}")
        if not steps:
            steps.append("No steps defined")
        return steps
