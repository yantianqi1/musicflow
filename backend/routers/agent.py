import json
import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.user import User
from backend.services import agent_service
from backend.services.agent_voice_memory import (
    clear_role_memory,
    clear_user_memory,
    list_user_memory,
)


router = APIRouter(prefix="/api/agent", tags=["AI 助手"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    attachments: Optional[list[str]] = None


class ConfirmRequest(BaseModel):
    session_id: str
    selected_model: Optional[str] = None
    client_request_id: Optional[str] = None
    param_overrides: Optional[dict] = None


class CancelRequest(BaseModel):
    session_id: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    created_at: str


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

async def _sse_generator(event_gen):
    """Wrap an async generator of event dicts into SSE text lines."""
    try:
        async for event in event_gen:
            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False, default=str)
            yield f"event: {event_type}\ndata: {data}\n\n"
    except Exception as e:
        error_data = json.dumps({"message": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await agent_service.create_session(db, user, req.title)
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await agent_service.list_sessions(db, user)
    return [
        SessionResponse(
            id=s.id, title=s.title,
            created_at=s.created_at.isoformat(), updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/timeline")
async def get_timeline(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await agent_service.get_timeline(db, session_id, user)


@router.get("/sessions/{session_id}/messages")
async def get_messages_compat(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await agent_service.get_timeline(db, session_id, user)


@router.get("/sessions/{session_id}/state")
async def get_state(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await agent_service.get_state_snapshot(db, session_id, user)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await agent_service.delete_session(db, session_id, user)
    return {"success": True}


# ---------------------------------------------------------------------------
# Character-voice memory (user-scoped, persists across sessions)
# ---------------------------------------------------------------------------

@router.get("/voice-memory")
async def list_voice_memory(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await list_user_memory(db, user.id)
    return {"items": items}


@router.delete("/voice-memory")
async def clear_voice_memory(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    removed = await clear_user_memory(db, user.id)
    await db.commit()
    return {"cleared": removed}


@router.delete("/voice-memory/{role_key:path}")
async def clear_voice_memory_role(
    role_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    removed = await clear_role_memory(db, user.id, role_key)
    await db.commit()
    return {"cleared": removed}


# ---------------------------------------------------------------------------
# Chat (SSE streaming)
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_gen = agent_service.chat(req.session_id, req.message, db, user, attachment_ids=req.attachments or [])
    return StreamingResponse(
        _sse_generator(event_gen),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Confirm tool execution (SSE streaming)
# ---------------------------------------------------------------------------

@router.post("/tool-calls/{tool_call_id:path}/confirm")
async def confirm_tool(
    tool_call_id: str,
    req: ConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_gen = agent_service.confirm_tool(
        req.session_id,
        tool_call_id,
        req.selected_model,
        db,
        user,
        client_request_id=req.client_request_id or str(uuid.uuid4()),
        param_overrides=req.param_overrides,
    )
    return StreamingResponse(
        _sse_generator(event_gen),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Cancel pending tool
# ---------------------------------------------------------------------------

@router.post("/tool-calls/{tool_call_id:path}/cancel")
async def cancel_tool(
    tool_call_id: str,
    req: CancelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await agent_service.cancel_tool(req.session_id, tool_call_id, db, user)


@router.post("/uploads")
async def upload_attachment(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attachment = await agent_service.upload_attachment(db, session_id, file, user)
    return attachment
