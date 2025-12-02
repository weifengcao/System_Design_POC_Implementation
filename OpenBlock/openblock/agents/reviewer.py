from __future__ import annotations

from dataclasses import dataclass

from .base import BaseAgent
from ..config import TaskConfig
from .executor import ExecutionResult


@dataclass
class Review:
    verdict: str
    message: str

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "message": self.message}


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="reviewer")

    def review(self, task: TaskConfig, execution: ExecutionResult) -> Review:
        if not execution.command_results:
            return Review(
                verdict="skipped",
                message=f"{task.name}: no commands to run",
            )
        if execution.success():
            return Review(
                verdict="pass",
                message=f"{task.name}: all commands succeeded",
            )
        failed = [r for r in execution.command_results if r.exit_code != 0]
        failed_cmds = ", ".join(cmd.command for cmd in failed)
        return Review(
            verdict="fail",
            message=f"{task.name}: failed commands -> {failed_cmds}",
        )
