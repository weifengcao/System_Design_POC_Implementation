from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List
import yaml


@dataclass
class CodeArtifact:
    path: str
    template: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskConfig:
    name: str
    description: str
    commands: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    code: List[CodeArtifact] = field(default_factory=list)


@dataclass
class ProjectConfig:
    name: str
    goal: str
    environment: Dict[str, Any] = field(default_factory=dict)
    tasks: List[TaskConfig] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "ProjectConfig":
        project_data = data.get("project") or {}
        env_data = data.get("environment") or {}
        task_entries = data.get("tasks") or []

        tasks = []
        for raw in task_entries:
            code_entries = raw.get("code", [])
            artifacts = []
            for code_entry in code_entries:
                artifacts.append(
                    CodeArtifact(
                        path=code_entry.get("path", ""),
                        template=code_entry.get("template", ""),
                        context=code_entry.get("context", {}),
                    )
                )
            tasks.append(
                TaskConfig(
                    name=raw.get("name", "task"),
                    description=raw.get("description", ""),
                    commands=raw.get("commands", []),
                    metadata=raw.get("metadata", {}),
                    code=artifacts,
                )
            )

        return cls(
            name=project_data.get("name", "Unnamed Project"),
            goal=project_data.get("goal", ""),
            environment=env_data,
            tasks=tasks,
        )


def load_config(path: Path) -> ProjectConfig:
    if not path.exists():
        raise FileNotFoundError(f"Plan file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ProjectConfig.from_mapping(data)
