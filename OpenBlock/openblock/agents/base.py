from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..config import TaskConfig


class Agent(Protocol):
    def name(self) -> str: ...


@dataclass
class BaseAgent:
    agent_name: str

    def name(self) -> str:
        return self.agent_name
