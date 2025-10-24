from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class TaskState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    name: str
    state: TaskState = TaskState.PENDING
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Workflow:
    conversation_id: str
    tasks: Dict[str, Task]


class WorkflowEngine:
    def __init__(self) -> None:
        self._workflows: Dict[str, Workflow] = {}

    def create(self, conversation_id: str, task_names: List[str]) -> Workflow:
        workflow = Workflow(
            conversation_id=conversation_id,
            tasks={name: Task(name=name) for name in task_names},
        )
        self._workflows[conversation_id] = workflow
        return workflow

    def update(self, conversation_id: str, task_name: str, new_state: TaskState, **metadata: str) -> Workflow:
        workflow = self._workflows[conversation_id]
        task = workflow.tasks[task_name]
        task.state = new_state
        if metadata:
            task.metadata.update(metadata)
        return workflow

    def get(self, conversation_id: str) -> Workflow:
        return self._workflows[conversation_id]

