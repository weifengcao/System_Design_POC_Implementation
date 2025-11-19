"""
Simple JSON-based persistence for the LLMChatroom POC.
Not suitable for production but demonstrates how we could snapshot service state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PersistedState:
    users: List[dict]
    rooms: List[dict]


class PersistentStore:
    def __init__(self, path: str = "LLMChatRoom/state.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> PersistedState:
        if not self.path.exists():
            return PersistedState(users=[], rooms=[])
        data = json.loads(self.path.read_text())
        return PersistedState(users=data.get("users", []), rooms=data.get("rooms", []))

    def persist(self, users: Dict[str, object], rooms: Dict[str, object]) -> None:
        payload = {
            "users": [asdict(user) for user in users.values()],
            "rooms": [self._serialize_room(room) for room in rooms.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2))

    def _serialize_room(self, room: object) -> dict:
        room_dict = asdict(room)
        # Dataclasses convert datetime to isoformat? asdict won't; convert manually.
        for msg in room_dict.get("messages", []):
            if hasattr(msg.get("created_at"), "isoformat"):
                msg["created_at"] = msg["created_at"].isoformat()
        return room_dict


def rehydrate_datetime(value: Optional[str]):
    if not value:
        return None
    from datetime import datetime

    return datetime.fromisoformat(value)
