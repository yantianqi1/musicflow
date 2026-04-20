import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent_message import AgentMessage, MessageRole
from backend.models.agent_tool_call import AgentToolCall, AgentToolCallStatus
from backend.models.agent_session import AgentSession, AgentSessionStatus
from backend.services.agent_state_service import mark_session_status, serialize_tool_call
from backend.services.agent_tools import get_tool


def normalize_tool_calls(raw_tool_calls: list[dict] | None) -> list[dict]:
    return raw_tool_calls or []


def select_actionable_tool_calls(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    paid_calls = []
    free_calls = []
    warnings = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("function", {}).get("name", "")
        tool_def = get_tool(tool_name)
        if tool_def is None:
            warnings.append(f"未知工具已忽略: {tool_name}")
            continue
        if tool_def.require_confirmation:
            paid_calls.append(tool_call)
        else:
            free_calls.append(tool_call)

    if len(paid_calls) > 1:
        warnings.append("同一轮只保留第一个需确认工具，其余收费工具已忽略。")
        paid_calls = paid_calls[:1]
    if paid_calls:
        if free_calls:
            warnings.append("检测到免费工具与收费工具混合调用，已只保留第一个收费工具。")
        return paid_calls, warnings
    return free_calls, warnings


async def create_tool_call_record(
    db: AsyncSession,
    session: AgentSession,
    message: AgentMessage | None,
    tool_name: str,
    tool_params: dict,
    tool_call_id: str | None = None,
) -> AgentToolCall:
    tool_call = AgentToolCall(
        id=tool_call_id,
        session_id=session.id,
        message_id=message.id if message else None,
        tool_name=tool_name,
        tool_params=tool_params,
    )
    db.add(tool_call)
    await db.flush()
    return tool_call


async def get_active_tool_call(db: AsyncSession, session: AgentSession) -> AgentToolCall | None:
    if not session.active_tool_call_id:
        return None
    result = await db.execute(
        select(AgentToolCall).where(
            AgentToolCall.id == session.active_tool_call_id,
            AgentToolCall.session_id == session.id,
        )
    )
    return result.scalar_one_or_none()


async def get_tool_call(db: AsyncSession, session_id: str, tool_call_id: str) -> AgentToolCall | None:
    result = await db.execute(
        select(AgentToolCall).where(
            AgentToolCall.id == tool_call_id,
            AgentToolCall.session_id == session_id,
        )
    )
    return result.scalar_one_or_none()


async def build_timeline(db: AsyncSession, session_id: str) -> list[dict]:
    messages = await _list_messages(db, session_id)
    tool_calls = await _list_tool_calls(db, session_id)
    items = [
        _message_to_timeline(message)
        for message in messages
        if message.role not in {MessageRole.system, MessageRole.tool}
    ]
    items.extend(_tool_call_to_timeline(tool_call) for tool_call in tool_calls)
    return sorted(items, key=lambda item: item["created_at"])


async def _list_messages(db: AsyncSession, session_id: str) -> list[AgentMessage]:
    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at)
    )
    return list(result.scalars().all())


async def _list_tool_calls(db: AsyncSession, session_id: str) -> list[AgentToolCall]:
    result = await db.execute(
        select(AgentToolCall)
        .where(AgentToolCall.session_id == session_id)
        .order_by(AgentToolCall.created_at)
    )
    return list(result.scalars().all())


def _message_to_timeline(message: AgentMessage) -> dict:
    return {
        "id": message.id,
        "type": "message",
        "role": message.role.value,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


def _tool_call_to_timeline(tool_call: AgentToolCall) -> dict:
    return {
        "id": tool_call.id,
        "type": "tool_call",
        "role": "tool_call" if tool_call.status in {AgentToolCallStatus.pending, AgentToolCallStatus.executing} else "tool_result",
        "tool_name": tool_call.tool_name,
        "params": tool_call.tool_params,
        "status": tool_call.status.value,
        "result": tool_call.result_payload,
        "error_message": tool_call.error_message,
        "created_at": tool_call.created_at.isoformat(),
    }
