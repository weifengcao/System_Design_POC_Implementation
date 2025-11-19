import asyncio
from typing import Any

class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    async def run(self):
        """Main loop for the agent."""
        raise NotImplementedError

    def log(self, message: str):
        print(f"[{self.name}] {message}")
