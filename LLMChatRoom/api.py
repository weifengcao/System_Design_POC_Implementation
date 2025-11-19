"""
FastAPI layer exposing the chat service.
Run with: `uvicorn LLMChatRoom.api:app --reload`
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from poc import ChatService, PersistentStore  # reuse service + persistence


class UserRequest(BaseModel):
    name: str
    roles: list[str] | None = None


class RoomRequest(BaseModel):
    name: str
    owner_id: str
    is_private: bool = True


class MemberRequest(BaseModel):
    user_id: str
    role: str = "member"


class MessageRequest(BaseModel):
    user_id: str
    body: str


class AgentRequest(BaseModel):
    name: str
    trigger_mode: str = "mention"


store = PersistentStore("LLMChatRoom/api_state.json")
service = ChatService(store=store)

app = FastAPI(title="LLM Chatroom API", version="0.1")


@app.post("/users")
def register_user(req: UserRequest):
    user = service.register_user(req.name, req.roles)
    return user.__dict__


@app.post("/rooms")
def create_room(req: RoomRequest):
    if req.owner_id not in service.users:
        raise HTTPException(status_code=404, detail="owner not found")
    room = service.create_room(req.name, req.owner_id, req.is_private)
    return {"room_id": room.room_id, "name": room.name}


@app.post("/rooms/{room_id}/members")
def add_member(room_id: str, req: MemberRequest):
    if req.user_id not in service.users:
        raise HTTPException(status_code=404, detail="user not found")
    service.add_member(room_id, req.user_id, req.role)
    return {"room_id": room_id, "user_id": req.user_id, "role": req.role}


@app.post("/rooms/{room_id}/agent")
def attach_agent(room_id: str, req: AgentRequest):
    service.attach_agent(room_id, req.name, req.trigger_mode)
    return {"room_id": room_id, "agent": req.name}


@app.post("/rooms/{room_id}/messages")
def send_message(room_id: str, req: MessageRequest):
    try:
        msg = service.send_message(room_id, req.user_id, req.body)
        return {
            "message_id": msg.message_id,
            "sender": msg.sender_name,
            "body": msg.body,
            "metadata": msg.metadata,
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="user not allowed")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/rooms/{room_id}/messages")
def history(room_id: str, limit: int = 20):
    messages = service.get_history(room_id, limit)
    return [
        {
            "message_id": msg.message_id,
            "sender": msg.sender_name,
            "body": msg.body,
            "created_at": msg.created_at.isoformat(),
            "metadata": msg.metadata,
        }
        for msg in messages
    ]


@app.get("/audit")
def audit_tail(limit: int = 20):
    return service.get_audit_log()[-limit:]
