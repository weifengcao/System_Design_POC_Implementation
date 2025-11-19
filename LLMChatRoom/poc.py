"""
Extended proof-of-concept for an LLM-enabled chatroom.
- Users/rooms/messages with ACLs and moderation guardrails.
- Rolling memory summarizes history for LLM prompts.
- Streaming LLM simulator plus audit log for prompts/responses.
- JSON-based persistence to mimic a backing store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import itertools
import json
import textwrap
import uuid

from storage import PersistentStore, rehydrate_datetime


# ---------- Domain models ----------


@dataclass
class User:
    user_id: str
    name: str
    roles: List[str]


@dataclass
class Message:
    message_id: str
    room_id: str
    sender_id: str
    sender_name: str
    body: str
    created_at: datetime
    redacted: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentConfig:
    agent_id: str
    name: str
    trigger_mode: str = "mention"  # "mention" or "all"
    summary_window: int = 5


@dataclass
class Room:
    room_id: str
    name: str
    owner_id: str
    is_private: bool
    members: Dict[str, str]  # user_id -> role
    messages: List[Message] = field(default_factory=list)
    agent: Optional[AgentConfig] = None
    summary: str = ""


@dataclass
class ModerationResult:
    body: str
    redacted: bool
    risk_score: float
    reason: str


@dataclass
class AuditEntry:
    event_type: str
    payload: Dict[str, str]
    created_at: datetime


# ---------- Support services ----------


class AuditLog:
    """Stores audit events in-memory and persists alongside service state."""

    def __init__(self) -> None:
        self.entries: List[AuditEntry] = []

    def record(self, event_type: str, payload: Dict[str, str]) -> None:
        self.entries.append(AuditEntry(event_type, payload, datetime.now(timezone.utc)))

    def export(self) -> List[Dict[str, str]]:
        return [
            {
                "event_type": entry.event_type,
                "payload": entry.payload,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in self.entries
        ]


class ModerationEngine:
    """Keyword filtering + heuristic risk scoring to mimic moderation pipeline."""

    def __init__(self, banned_keywords: Optional[List[str]] = None) -> None:
        self.banned_keywords = {kw.lower() for kw in (banned_keywords or ["ssn", "password"])}

    def inspect(self, body: str) -> ModerationResult:
        redacted = False
        sanitized_words = []
        risk_score = 0.05
        reason = "clean"
        for token in body.split():
            token_lower = token.lower()
            if token_lower in self.banned_keywords:
                sanitized_words.append("[redacted]")
                redacted = True
                risk_score = 0.95
                reason = f"contains banned keyword '{token_lower}'"
            elif token_lower.startswith("http"):
                risk_score = max(risk_score, 0.35)
                sanitized_words.append(token)
                reason = "contains link"
            else:
                sanitized_words.append(token)
        if any(char.isdigit() for char in body) and len(body) > 10:
            risk_score = max(risk_score, 0.5)
            reason = "possible PII digits"
        return ModerationResult(" ".join(sanitized_words), redacted, risk_score, reason)


class MemoryManager:
    """Maintains rolling summaries and returns context windows."""

    def __init__(self) -> None:
        self.summary_cache: Dict[str, str] = {}

    def update_memory(self, room: Room, window: int) -> None:
        recent = room.messages[-window:]
        if not recent:
            return
        bullets = []
        for msg in recent:
            body = msg.body.replace("\n", " ")[:160]
            bullets.append(f"- {msg.sender_name}: {body}")
        summary = textwrap.dedent(
            f"""
            Room '{room.name}' summary:
            Last {len(recent)} highlights:
            {chr(10).join(bullets)}
            """
        ).strip()
        room.summary = summary
        self.summary_cache[room.room_id] = summary

    def get_context(self, room: Room, limit: int = 6) -> str:
        history = room.messages[-limit:]
        formatted = "\n".join(
            f"[{m.created_at.strftime('%H:%M:%S')}] {m.sender_name}: {m.body}" for m in history
        )
        summary = self.summary_cache.get(room.room_id, "")
        return f"{summary}\nRecent messages:\n{formatted}".strip()


class LLMAdapter:
    def stream_response(self, payload: Dict[str, str]) -> Iterable[str]:
        raise NotImplementedError


class StreamingLLMSimulator(LLMAdapter):
    """Mimics a provider sending streaming tokens back to the orchestrator."""

    def stream_response(self, payload: Dict[str, str]) -> Iterable[str]:
        template = textwrap.dedent(
            f"""
            Hi {payload['triggered_by']}, I'm tracking this room.
            Summary insight: {payload['summary'][:160]}
            Key observations: {payload['context'][:200]}
            Suggested plan: {payload['actions']}
            """
        ).strip()
        for sentence in template.split("\n"):
            yield sentence.strip() + " "


class LLMAgentRuntime:
    """Builds prompts, calls adapter, and records audit trail."""

    def __init__(
        self,
        config: AgentConfig,
        memory_manager: MemoryManager,
        adapter: LLMAdapter,
        audit_log: AuditLog,
    ) -> None:
        self.config = config
        self.memory = memory_manager
        self.adapter = adapter
        self.audit = audit_log

    def should_trigger(self, message: Message) -> bool:
        if self.config.trigger_mode == "all":
            return message.sender_id != self.config.agent_id
        return f"@{self.config.name.lower()}" in message.body.lower()

    def respond(self, room: Room, trigger_message: Message) -> Message:
        context = self.memory.get_context(room)
        payload = {
            "room": room.name,
            "summary": room.summary,
            "context": context,
            "triggered_by": trigger_message.sender_name,
            "actions": self._extract_action_items(room),
        }
        self.audit.record(
            "llm.prompt",
            {
                "agent": self.config.name,
                "room_id": room.room_id,
                "prompt_tokens": str(len(context.split())),
            },
        )
        chunks = list(self.adapter.stream_response(payload))
        body = "".join(chunks).strip()
        self.audit.record(
            "llm.response",
            {"agent": self.config.name, "room_id": room.room_id, "chunks": str(len(chunks))},
        )
        return Message(
            message_id=uuid.uuid4().hex,
            room_id=room.room_id,
            sender_id=self.config.agent_id,
            sender_name=self.config.name,
            body=body,
            created_at=datetime.now(timezone.utc),
        )

    def _extract_action_items(self, room: Room) -> str:
        tasks = [
            msg.body
            for msg in room.messages[-8:]
            if any(prefix in msg.body.lower() for prefix in ("todo", "action", "next", "plan"))
        ]
        if not tasks:
            return "No explicit tasks detected."
        return "; ".join(tasks[:3])


# ---------- Chat service ----------


class ChatService:
    """Core orchestrator for rooms, ACLs, persistence, moderation, and agent triggers."""

    def __init__(
        self,
        store: Optional[PersistentStore] = None,
        adapter: Optional[LLMAdapter] = None,
    ) -> None:
        self.users: Dict[str, User] = {}
        self.rooms: Dict[str, Room] = {}
        self.mod_engine = ModerationEngine()
        self.memory = MemoryManager()
        self.audit = AuditLog()
        self.store = store
        self.adapter = adapter or StreamingLLMSimulator()
        self._id_counter = itertools.count(1)
        if self.store:
            self._load_state(self.store.load())

    # ---- User & room management ----

    def register_user(self, name: str, roles: Optional[List[str]] = None) -> User:
        user = User(user_id=uuid.uuid4().hex, name=name, roles=roles or ["member"])
        self.users[user.user_id] = user
        self._persist()
        self.audit.record("user.registered", {"user_id": user.user_id, "name": user.name})
        return user

    def create_room(self, name: str, owner_id: str, is_private: bool = True) -> Room:
        room = Room(
            room_id=uuid.uuid4().hex,
            name=name,
            owner_id=owner_id,
            is_private=is_private,
            members={owner_id: "owner"},
        )
        self.rooms[room.room_id] = room
        self._persist()
        self.audit.record("room.created", {"room_id": room.room_id, "owner_id": owner_id})
        return room

    def add_member(self, room_id: str, user_id: str, role: str = "member") -> None:
        room = self._get_room(room_id)
        room.members[user_id] = role
        self._persist()

    def attach_agent(self, room_id: str, agent_name: str, trigger_mode: str = "mention") -> None:
        room = self._get_room(room_id)
        config = AgentConfig(
            agent_id=uuid.uuid4().hex, name=agent_name, trigger_mode=trigger_mode, summary_window=5
        )
        room.agent = config
        self._persist()

    # ---- Messaging ----

    def send_message(self, room_id: str, user_id: str, body: str) -> Message:
        room = self._get_room(room_id)
        self._ensure_member(room, user_id)
        moderation = self.mod_engine.inspect(body)
        user = self.users[user_id]
        message = Message(
            message_id=uuid.uuid4().hex,
            room_id=room_id,
            sender_id=user_id,
            sender_name=user.name,
            body=moderation.body,
            created_at=datetime.now(timezone.utc),
            redacted=moderation.redacted,
            metadata={
                "risk_score": f"{moderation.risk_score:.2f}",
                "moderation_reason": moderation.reason,
            },
        )
        room.messages.append(message)
        self.audit.record(
            "message.stored",
            {
                "room_id": room_id,
                "message_id": message.message_id,
                "risk_score": message.metadata["risk_score"],
            },
        )
        agent_msg: Optional[Message] = None
        if room.agent:
            self.memory.update_memory(room, room.agent.summary_window)
            runtime = LLMAgentRuntime(room.agent, self.memory, self.adapter, self.audit)
            if runtime.should_trigger(message):
                agent_msg = runtime.respond(room, message)
                room.messages.append(agent_msg)
        self._persist()
        return agent_msg or message

    def get_history(self, room_id: str, limit: int = 20) -> List[Message]:
        room = self._get_room(room_id)
        return room.messages[-limit:]

    def get_audit_log(self) -> List[Dict[str, str]]:
        return self.audit.export()

    # ---- Helpers ----

    def _get_room(self, room_id: str) -> Room:
        if room_id not in self.rooms:
            raise ValueError("Room not found")
        return self.rooms[room_id]

    def _ensure_member(self, room: Room, user_id: str) -> None:
        if user_id not in room.members:
            raise PermissionError("User not allowed in this room")

    def _persist(self) -> None:
        if self.store:
            self.store.persist(self.users, self.rooms)

    def _load_state(self, state) -> None:
        for user_payload in state.users:
            user = User(**user_payload)
            self.users[user.user_id] = user
        for room_payload in state.rooms:
            agent_payload = room_payload.get("agent")
            agent_config = AgentConfig(**agent_payload) if agent_payload else None
            messages = []
            for msg_payload in room_payload.get("messages", []):
                metadata = msg_payload.get("metadata") or {}
                created_at = rehydrate_datetime(msg_payload.get("created_at")) or datetime.now(timezone.utc)
                messages.append(
                    Message(
                        message_id=msg_payload["message_id"],
                        room_id=msg_payload["room_id"],
                        sender_id=msg_payload["sender_id"],
                        sender_name=msg_payload["sender_name"],
                        body=msg_payload["body"],
                        created_at=created_at,
                        redacted=msg_payload.get("redacted", False),
                        metadata=metadata,
                    )
                )
            room = Room(
                room_id=room_payload["room_id"],
                name=room_payload["name"],
                owner_id=room_payload["owner_id"],
                is_private=room_payload.get("is_private", True),
                members=room_payload.get("members", {}),
                agent=agent_config,
                messages=messages,
                summary=room_payload.get("summary", ""),
            )
            self.rooms[room.room_id] = room


# ---------- Demo runner ----------


def run_demo() -> None:
    state_path = Path("LLMChatRoom/demo_state.json")
    if state_path.exists():
        state_path.unlink()
    store = PersistentStore(str(state_path))
    service = ChatService(store=store)

    # Users
    alice = service.register_user("Alice", roles=["admin"])
    bob = service.register_user("Bob")
    chloe = service.register_user("Chloe")

    # Secure room
    room = service.create_room("launch-war-room", owner_id=alice.user_id, is_private=True)
    service.add_member(room.room_id, bob.user_id)
    service.add_member(room.room_id, chloe.user_id)
    service.attach_agent(room.room_id, agent_name="Orion", trigger_mode="mention")

    # Conversation
    script = [
        (alice, "Welcome team. @Orion keep track of action items."),
        (bob, "TODO finalize onboarding spec by Friday."),
        (chloe, "Next: schedule dry-run with Sales."),
        (bob, "Reminder: never share password or SSN in chat."),
        (alice, "@orion summarize current plan."),
    ]
    for user, text in script:
        service.send_message(room.room_id, user.user_id, text)

    # History dump
    print("\n=== Chat History ===")
    for msg in service.get_history(room.room_id):
        marker = "(redacted)" if msg.redacted else ""
        print(
            f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.sender_name}: {msg.body} "
            f"[risk={msg.metadata.get('risk_score','0')}]{marker}"
        )

    # Show memory summary
    print("\n=== Memory Summary ===")
    print(room.summary)

    # Demonstrate security constraint
    try:
        outsider = service.register_user("Mallory")
        service.send_message(room.room_id, outsider.user_id, "hello?")
    except PermissionError as exc:
        print("\nSecurity check (expected failure):", exc)

    print("\n=== Audit Log Sample ===")
    print(json.dumps(service.get_audit_log()[-4:], indent=2))


if __name__ == "__main__":
    run_demo()
