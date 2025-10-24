from __future__ import annotations

from typing import Dict


class IdempotencyTracker:
    def __init__(self) -> None:
        self._seen: Dict[str, str] = {}

    def check(self, key: str, value: str) -> bool:
        if key in self._seen:
            return False
        self._seen[key] = value
        return True

