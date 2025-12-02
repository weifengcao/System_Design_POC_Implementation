from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .base import BaseAgent
from ..config import CodeArtifact, ProjectConfig, TaskConfig


@dataclass
class ArtifactResult:
    path: Path
    created: bool
    content: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "created": self.created,
            "error": self.error,
        }


@dataclass
class CodingResult:
    task_name: str
    artifacts: List[ArtifactResult] = field(default_factory=list)

    def success(self) -> bool:
        return all(artifact.error is None for artifact in self.artifacts)

    def to_dict(self) -> dict:
        return {
            "task": self.task_name,
            "success": self.success(),
            "artifacts": [a.to_dict() for a in self.artifacts],
        }


class AICodingAgent(BaseAgent):
    def __init__(self, project: ProjectConfig, base_dir: Path | None = None):
        super().__init__(agent_name="ai_coder")
        self.project = project
        self.base_dir = base_dir or Path.cwd()

    def generate(self, task: TaskConfig) -> CodingResult | None:
        if not task.code:
            return None
        artifacts: List[ArtifactResult] = []
        for artifact in task.code:
            result = self._write_artifact(task, artifact)
            artifacts.append(result)
        return CodingResult(task_name=task.name, artifacts=artifacts)

    def _render_template(self, task: TaskConfig, artifact: CodeArtifact) -> str:
        context: Dict[str, str] = {
            "project_name": self.project.name,
            "project_goal": self.project.goal,
            "task_name": task.name,
            "task_description": task.description,
        }
        context.update({k: str(v) for k, v in task.metadata.items()})
        context.update({k: str(v) for k, v in artifact.context.items()})
        try:
            return artifact.template.format(**context)
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(f"Missing template variable '{missing}' in artifact {artifact.path}") from exc

    def _write_artifact(self, task: TaskConfig, artifact: CodeArtifact) -> ArtifactResult:
        target_path = (self.base_dir / artifact.path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = self._render_template(task, artifact)
            target_path.write_text(content, encoding="utf-8")
            return ArtifactResult(path=target_path, created=True, content=content)
        except Exception as exc:  # pragma: no cover - defensive
            return ArtifactResult(path=target_path, created=False, error=str(exc))
