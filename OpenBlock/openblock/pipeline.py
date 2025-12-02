from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import json

from .config import ProjectConfig, TaskConfig, load_config
from .agents.planner import PlannerAgent
from .agents.executor import ExecutorAgent, ExecutionResult
from .agents.reviewer import ReviewerAgent, Review
from .agents.coder import AICodingAgent, CodingResult


@dataclass
class TaskRun:
    task: TaskConfig
    plan_steps: List[str]
    coding: CodingResult | None
    execution: ExecutionResult
    review: Review


class PipelineRunner:
    def __init__(
        self,
        config: ProjectConfig,
        log_dir: Path | None = None,
        dry_run: bool = False,
        workspace: Path | None = None,
    ):
        self.config = config
        self.log_dir = log_dir or Path(".openblock/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self.workspace = workspace or Path.cwd()
        self.planner = PlannerAgent()
        self.coder = AICodingAgent(project=self.config, base_dir=self.workspace)
        self.executor = ExecutorAgent()
        self.reviewer = ReviewerAgent()
        self.task_runs: List[TaskRun] = []

    @classmethod
    def from_file(cls, plan_path: Path, **kwargs) -> "PipelineRunner":
        config = load_config(plan_path)
        workspace = kwargs.pop("workspace", plan_path.parent.resolve())
        return cls(config=config, workspace=workspace, **kwargs)

    def execute(self) -> List[TaskRun]:
        for task in self.config.tasks:
            plan_steps = self.planner.plan(task)
            coding = self.coder.generate(task)
            execution = self.executor.execute(task, dry_run=self.dry_run)
            review = self.reviewer.review(task, execution)
            run = TaskRun(
                task=task,
                plan_steps=plan_steps,
                coding=coding,
                execution=execution,
                review=review,
            )
            self.task_runs.append(run)
        self._persist_run()
        return self.task_runs

    def _persist_run(self) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        payload = {
            "project": {"name": self.config.name, "goal": self.config.goal},
            "dry_run": self.dry_run,
            "tasks": [
                {
                    "name": run.task.name,
                    "plan_steps": run.plan_steps,
                    "coding": run.coding.to_dict() if run.coding else None,
                    "execution": run.execution.to_dict(),
                    "review": run.review.to_dict(),
                }
                for run in self.task_runs
            ],
        }
        outfile = self.log_dir / f"run-{timestamp}.json"
        with outfile.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
