from backend.models.agent_session import AgentSession, AgentSessionStatus
from backend.models.agent_tool_call import AgentToolCall, AgentToolCallStatus
from backend.models.generation import Generation, GenerationStatus, derive_generation_title
from backend.models.voice import Voice
from backend.models.user import User
from backend.services.agent_state_service import mark_session_status
from backend.services.agent_tools import AgentToolDef
from backend.services.agent_voice_memory import save_memory_from_tool_params
from backend.services.billing_service import check_and_deduct, refund_credits


def _format_exception(exc: Exception) -> str:
    """Best-effort human message — str(HTTPException) is empty so use .detail."""
    from fastapi import HTTPException
    import httpx
    if isinstance(exc, HTTPException):
        return str(exc.detail) if exc.detail else f"HTTP {exc.status_code}"
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            body = exc.response.text[:300]
        except Exception:
            body = ""
        return f"上游 HTTP {exc.response.status_code}: {body}"
    if isinstance(exc, httpx.RequestError):
        return f"{type(exc).__name__}: {exc!s}"
    msg = str(exc).strip()
    return msg or f"{type(exc).__name__}(无错误信息)"


def _merge_tool_params(tool_call: AgentToolCall, selected_model: str | None, param_overrides: dict | None) -> dict:
    params = dict(tool_call.tool_params or {})
    if selected_model:
        params["model"] = selected_model
    if param_overrides:
        params.update(param_overrides)
    return params


def _build_generation(tool_def: AgentToolDef, tool_params: dict, user: User, cost: int) -> Generation:
    return Generation(
        user_id=user.id,
        service_type=tool_def.service_type,
        model=tool_params.get("model"),
        credits_cost=cost,
        params=tool_params,
        title=derive_generation_title(tool_def.service_type, tool_params, None),
    )


async def cancel_tool_call(db, session: AgentSession, tool_call: AgentToolCall) -> AgentToolCall:
    tool_call.status = AgentToolCallStatus.cancelled
    mark_session_status(session, AgentSessionStatus.cancelled, None)
    await db.commit()
    await db.refresh(tool_call)
    return tool_call


async def _execute_and_store_result(db, user: User, tool_call: AgentToolCall, tool_def: AgentToolDef, tool_params: dict):
    result = await tool_def.executor(tool_params, db, user)
    tool_call.result_payload = result
    tool_call.error_message = None
    tool_call.status = AgentToolCallStatus.succeeded
    return result


async def _upsert_voice_record(db, user: User, tool_name: str, tool_params: dict, result: dict):
    voice_id = result.get("voice_id")
    if tool_name not in {"clone_voice", "design_voice"} or not voice_id:
        return
    db.add(Voice(
        user_id=user.id,
        voice_id=voice_id,
        voice_type="cloned" if tool_name == "clone_voice" else "designed",
        name=tool_params.get("voice_id") if tool_name == "clone_voice" else None,
        description=tool_params.get("prompt", "")[:500] if tool_name == "design_voice" else None,
    ))


async def execute_tool_call(
    db,
    user: User,
    session: AgentSession,
    tool_call: AgentToolCall,
    tool_def: AgentToolDef,
    client_request_id: str,
    selected_model: str | None = None,
    param_overrides: dict | None = None,
) -> dict:
    if tool_call.status == AgentToolCallStatus.succeeded and tool_call.idempotency_key == client_request_id:
        return {"status": "succeeded", "replayed": True, "result": tool_call.result_payload}

    if tool_call.status != AgentToolCallStatus.pending:
        return {"status": tool_call.status.value, "replayed": False, "result": tool_call.result_payload}

    tool_params = _merge_tool_params(tool_call, selected_model, param_overrides)
    tool_call.idempotency_key = client_request_id
    tool_call.selected_model = tool_params.get("model")
    tool_call.status = AgentToolCallStatus.executing
    mark_session_status(session, AgentSessionStatus.executing, tool_call.id)

    cost, free_used, generation = await _prepare_execution(db, user, tool_call, tool_def, tool_params)
    try:
        result = await _execute_and_store_result(db, user, tool_call, tool_def, tool_params)
        _finalize_generation(generation, tool_def, tool_params, result)
        await _upsert_voice_record(db, user, tool_call.tool_name, tool_params, result)
        if tool_call.tool_name == "batch_voice_over":
            await save_memory_from_tool_params(
                db, user.id, tool_params,
                session_id=tool_call.session_id, source="user",
            )
        mark_session_status(session, AgentSessionStatus.completed, None)
        await db.commit()
        return {"status": "succeeded", "replayed": False, "result": result}
    except Exception as exc:
        await _handle_execution_failure(db, user, session, tool_call, tool_def, cost, free_used, generation, exc)
        return {"status": "failed", "replayed": False, "result": {"error": _format_exception(exc)}}


async def _prepare_execution(db, user, tool_call, tool_def, tool_params):
    cost = 0
    free_used = 0
    generation = None
    if tool_def.service_type:
        char_count = _count_billable_chars(tool_params)
        cost, free_used, _ = await check_and_deduct(
            db, user, tool_def.service_type, tool_params.get("model"), char_count
        )
        tool_call.credits_cost = cost
        generation = _build_generation(tool_def, tool_params, user, cost)
        db.add(generation)
        await db.flush()
    return cost, free_used, generation


def _count_billable_chars(tool_params: dict) -> int:
    if "segments" in tool_params:
        return sum(len(item.get("text", "")) for item in tool_params.get("segments", []))
    return len(tool_params.get("text", ""))


def _finalize_generation(generation: Generation | None, tool_def: AgentToolDef, tool_params: dict, result: dict) -> None:
    if generation is None:
        return
    generation.status = GenerationStatus.success
    generation.result_url = result.get("audio_url") or result.get("trial_audio_url")
    generation.extra_info = result
    generation.title = derive_generation_title(tool_def.service_type, tool_params, result)


async def _handle_execution_failure(db, user, session, tool_call, tool_def, cost, free_used, generation, exc):
    import logging, traceback
    logger = logging.getLogger(__name__)
    err_msg = _format_exception(exc)
    logger.error("工具 %s 执行失败: %s\n%s", tool_call.tool_name, err_msg, traceback.format_exc())
    tool_call.status = AgentToolCallStatus.failed
    tool_call.error_message = err_msg
    tool_call.result_payload = {
        "error": err_msg,
        "refunded": cost if cost > 0 else 0,
        "refunded_free": free_used if cost > 0 else 0,
        "refunded_paid": max(cost - free_used, 0) if cost > 0 else 0,
    }
    next_status = AgentSessionStatus.awaiting_confirmation if tool_def.require_confirmation else AgentSessionStatus.completed
    next_active_tool = tool_call.id if tool_def.require_confirmation else None
    mark_session_status(session, next_status, next_active_tool)
    if generation is not None:
        generation.status = GenerationStatus.failed
    if cost > 0:
        await refund_credits(db, user, cost, tool_def.service_type, free_used, str(exc))
    await db.commit()
