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
class TaskRecord:
    name: str
    state: TaskState = TaskState.PENDING
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowState:
    po_id: str
    tasks: Dict[str, TaskRecord] = field(default_factory=dict)
    active_task: str | None = None


class WorkflowEngine:
    """Simplified Temporal-like state store for demonstration."""

    def __init__(self) -> None:
        self._workflows: Dict[str, WorkflowState] = {}

    def create_workflow(self, po_id: str, task_names: List[str]) -> WorkflowState:
        workflow = WorkflowState(
            po_id=po_id,
            tasks={name: TaskRecord(name=name) for name in task_names},
            active_task=task_names[0] if task_names else None,
        )
        self._workflows[po_id] = workflow
        return workflow

    def update_task(self, po_id: str, task_name: str, new_state: TaskState, **metadata: str) -> WorkflowState:
        workflow = self._workflows[po_id]
        task = workflow.tasks[task_name]
        task.state = new_state
        if metadata:
            task.metadata.update(metadata)
        workflow.active_task = self._next_task(workflow)
        return workflow

    def _next_task(self, workflow: WorkflowState) -> str | None:
        for name, record in workflow.tasks.items():
            if record.state == TaskState.PENDING:
                return name
        return None

    def get_workflow(self, po_id: str) -> WorkflowState:
        return self._workflows[po_id]

