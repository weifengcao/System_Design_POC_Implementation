from __future__ import annotations

from dataclasses import dataclass, field
from subprocess import CompletedProcess, run
from typing import List
import shlex

from .base import BaseAgent
from ..config import TaskConfig


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class ExecutionResult:
    task_name: str
    dry_run: bool
    command_results: List[CommandResult] = field(default_factory=list)

    def success(self) -> bool:
        return all(result.exit_code == 0 for result in self.command_results)

    def to_dict(self) -> dict:
        return {
            "task": self.task_name,
            "dry_run": self.dry_run,
            "success": self.success(),
            "commands": [
                {
                    "command": r.command,
                    "exit_code": r.exit_code,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                }
                for r in self.command_results
            ],
        }


class ExecutorAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="executor")

    def execute(self, task: TaskConfig, dry_run: bool = False) -> ExecutionResult:
        results: List[CommandResult] = []
        for command in task.commands:
            if dry_run:
                results.append(CommandResult(command, 0, "[dry-run]", ""))
                continue
            completed = self._run_command(command)
            results.append(
                CommandResult(
                    command=command,
                    exit_code=completed.returncode,
                    stdout=(completed.stdout or "").strip(),
                    stderr=(completed.stderr or "").strip(),
                )
            )
        return ExecutionResult(task_name=task.name, dry_run=dry_run, command_results=results)

    def _run_command(self, command: str) -> CompletedProcess:
        return run(
            command,
            shell=True,
            text=True,
            capture_output=True,
        )
