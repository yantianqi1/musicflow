from backend.models.agent_session import AgentSession, AgentSessionStatus
from backend.models.agent_tool_call import AgentToolCall


def build_state_snapshot(session: AgentSession, active_tool_call: AgentToolCall | None) -> dict:
    return {
        "session_id": session.id,
        "status": session.status.value,
        "active_tool_call": serialize_tool_call(active_tool_call),
        "last_round_id": session.last_round_id,
    }


def mark_session_status(
    session: AgentSession,
    status: AgentSessionStatus,
    active_tool_call_id: str | None = None,
) -> AgentSession:
    session.status = status
    session.active_tool_call_id = active_tool_call_id
    return session


def serialize_tool_call(tool_call: AgentToolCall | None) -> dict | None:
    if tool_call is None:
        return None
    return {
        "id": tool_call.id,
        "message_id": tool_call.message_id,
        "tool_name": tool_call.tool_name,
        "tool_params": tool_call.tool_params,
        "status": tool_call.status.value,
        "selected_model": tool_call.selected_model,
        "credits_cost": tool_call.credits_cost,
        "error_message": tool_call.error_message,
        "result_payload": tool_call.result_payload,
    }
