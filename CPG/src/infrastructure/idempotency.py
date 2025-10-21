from __future__ import annotations

from typing import Dict, Tuple


class IdempotencyRegistry:
    """Tracks processed operations to guard against duplicate events."""

    def __init__(self) -> None:
        self._seen: Dict[str, str] = {}

    def check_and_set(self, key: str, value: str) -> bool:
        if key in self._seen:
            return False
        self._seen[key] = value
        return True

