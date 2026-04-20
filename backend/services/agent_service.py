"""Agent orchestration service.

Manages conversation flow, LLM interaction, tool execution, and billing.
"""

from __future__ import annotations

import json
import uuid
import logging
import traceback
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from backend.models.user import User
from backend.models.agent_session import AgentSession, AgentSessionStatus
from backend.models.agent_message import AgentMessage, MessageRole
from backend.models.agent_tool_call import AgentToolCallStatus
from backend.services.llm_client import llm
from backend.services.agent_tools import (
    TOOL_REGISTRY, get_openai_tools, get_tool, get_tool_pricing,
)
from backend.services.agent_attachments import list_session_attachments, save_attachment
from backend.services.agent_orchestrator import (
    build_timeline,
    create_tool_call_record,
    get_active_tool_call,
    get_tool_call,
    normalize_tool_calls,
    select_actionable_tool_calls,
)
from backend.services.agent_prompt_builder import build_prompt
from backend.services.agent_skill_matcher import resolve_skills
from backend.services.agent_state_service import build_state_snapshot, mark_session_status, serialize_tool_call
from backend.services.agent_tool_executor import cancel_tool_call as cancel_tool_call_record
from backend.services.agent_tool_executor import execute_tool_call
from backend.services import voice_service
from backend.services.voice_casting import apply_role_voice_selection, enrich_batch_voice_over_params
from backend.services.agent_voice_memory import apply_memory_to_selection

logger = logging.getLogger(__name__)


def _format_llm_error(exc: Exception) -> str:
    """Best-effort extract a useful message from an LLM client exception."""
    import httpx
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            body = exc.response.text[:500]
        except Exception:
            body = "<no body>"
        return f"HTTP {exc.response.status_code} from LLM: {body}"
    if isinstance(exc, httpx.RequestError):
        return f"{type(exc).__name__}: {exc!s} (url={exc.request.url if exc.request else '?'})"
    msg = str(exc).strip()
    return msg or f"{type(exc).__name__}(无错误信息)"


class _DummyTool:
    require_confirmation = True

_DUMMY_TOOL = _DummyTool()


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------
# System prompt is now built dynamically from modular skills.
# See agent_skills.py for the registry and matching logic.
# Skills are defined in backend/services/skills/:
#   base.py, music_creation.py, speech_synthesis.py,
#   voice_over.py, voice_management.py, billing.py


# Fallback when MiniMax voice query fails
_FALLBACK_VOICE_LIST = """\
### 系统音色
旁白/叙述: male-qn-jingying(精英青年), male-qn-qingse(青涩青年), female-chengshu(成熟女性), presenter_male(男播音), presenter_female(女播音), audiobook_male_1(有声书男声), audiobook_male_2(有声书男声2), audiobook_female_1(有声书女声)
青年男性: male-qn-qingse(青涩), male-qn-jingying(精英), male-qn-badao(霸道), male-qn-daxuesheng(大学生)
女性: female-shaonv(少女), female-yujie(御姐), female-chengshu(成熟), female-tianmei(甜美)
特殊: clever_boy(机灵男孩), cute_boy(可爱男孩), lovely_girl(可爱女孩), Santa_Claus(圣诞老人)
Beta高质量版: 上述音色加 -jingpin 后缀，如 male-qn-jingying-jingpin"""


async def _build_voice_list() -> str:
    """Fetch voices from MiniMax and format for system prompt."""
    try:
        data = await voice_service.list_voices(voice_type="all")
        voices = data.get("voices", [])
    except Exception as e:
        logger.warning("Failed to fetch voice list: %s, using fallback", e)
        return _FALLBACK_VOICE_LIST

    if not voices:
        return _FALLBACK_VOICE_LIST

    system_voices = []
    custom_voices = []
    for v in voices:
        vid = v["voice_id"]
        name = v.get("voice_name") or vid
        desc = v.get("description") or ""
        label = f"{vid}({name})" if name != vid else vid
        if desc:
            label += f" - {desc[:30]}"

        if v.get("voice_type") == "system":
            system_voices.append(label)
        else:
            vtype = "克隆" if v.get("voice_type") == "cloned" else "AI设计"
            custom_voices.append(f"{label} [{vtype}]")

    parts = []
    if system_voices:
        parts.append("### 系统音色\n" + ", ".join(system_voices))
    if custom_voices:
        parts.append("### 用户自定义音色（优先考虑使用）\n" + ", ".join(custom_voices))
    else:
        parts.append("### 用户自定义音色\n（暂无，用户可通过克隆或AI设计创建专属音色）")

    return "\n\n".join(parts)


async def build_system_prompt(
    user: User,
    db: AsyncSession,
    session: AgentSession,
    user_message: str = "",
    conversation_context: list[dict] | None = None,
    attachments: list | None = None,
    active_tool_call=None,
) -> tuple[str, list[str]]:
    matched_skills = resolve_skills(
        user_message=user_message,
        conversation_context=conversation_context,
        attachments=attachments,
        session_status=session.status,
    )
    return await build_prompt(db, user, session, matched_skills, attachments or [], active_tool_call)


class _SafeFormatDict(dict):
    """Dict that returns the key placeholder for missing keys instead of raising."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


# ---------------------------------------------------------------------------
# Emotion diversity enforcement for batch_voice_over
# ---------------------------------------------------------------------------

_NARRATION_ROLES = {"旁白", "叙述者", "narrator", "旁白/叙述"}


def _enhance_text_params(segments: list[dict]):
    """Adjust speed/vol/pitch based on punctuation and text patterns."""
    import re as _re
    for seg in segments:
        text = seg.get("text", "")
        speed = seg.get("speed", 1.0)
        vol = seg.get("vol", 1.0)
        pitch = seg.get("pitch", 0)

        # Exclamation marks → boost speed & volume
        if "！" in text or "!" in text:
            seg["speed"] = round(min(2.0, speed * 1.08), 2)
            seg["vol"] = round(min(10.0, vol * 1.15), 2)

        # Ellipsis → slow down + insert pause after ellipsis
        if "……" in text or "..." in text:
            seg["speed"] = round(max(0.5, speed * 0.92), 2)
            text = _re.sub(r'(……|\.\.\.)', r'\1<#0.5#>', text)
            # Remove duplicate pauses
            text = _re.sub(r'(<#[\d.]+#>)\s*<#0\.5#>', r'\1', text)
            seg["text"] = text

        # Question mark → raise pitch slightly
        stripped = text.rstrip()
        if stripped.endswith("？") or stripped.endswith("?"):
            seg["pitch"] = min(12, pitch + 1)


_VOICE_DIRECTOR_PROMPT = """\
你是一位专业的有声书配音导演。下面是一段小说配音的 segments JSON。

请审查每一段的参数是否与文本内容匹配，返回修正后的完整 JSON 数组。

审查重点：
1. emotion 必须是以下之一：happy, sad, angry, fearful, disgusted, surprised, fluent, calm
   - 开心/得意→happy，悲伤/无奈/叹息→sad，愤怒/吼叫→angry
   - 紧张/犹豫/不安→fearful，惊讶/震惊→surprised，厌恶/不屑→disgusted
   - 日常对话/自然交流→fluent，纯客观陈述→calm
   - 任何单一 emotion 不应超过全部段落的 40%
2. speed：吼叫/紧急 1.1~1.3，悲伤/沉思 0.75~0.90，日常 0.95~1.05
3. vol：吼叫 1.5~2.5，低语/内心 0.5~0.7，正常 0.9~1.1，旁白 0.85~0.95
4. pitch：愤怒/威严 -2~-1，惊讶/年轻 +1~+3，正常 -1~+1
5. 旁白段落不应有语气标签如 (laughs) (chuckle)
6. 对话段中，根据叙述描写判断是否需要语气标签
7. 在转折、悬念、情感爆发前适当插入 <#x#> 停顿（0.3~1.5秒）

只返回 JSON 数组，不要任何解释文字。"""


async def _llm_review_segments(segments: list[dict]) -> list[dict] | None:
    """Use LLM to review and refine segment parameters. Returns None on failure."""
    try:
        segments_json = json.dumps(segments, ensure_ascii=False)
        result = await llm.chat([
            {"role": "system", "content": _VOICE_DIRECTOR_PROMPT},
            {"role": "user", "content": segments_json},
        ])
        content = result.get("content", "")
        # Extract JSON array from response (may have markdown fences)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        reviewed = json.loads(content)
        if not isinstance(reviewed, list) or len(reviewed) != len(segments):
            logger.warning("LLM review returned %d segments (expected %d), skipping",
                          len(reviewed) if isinstance(reviewed, list) else 0, len(segments))
            return None

        # Validate reviewed segments preserve text and role
        _VALID = {"happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm", "fluent"}
        for i, (orig, rev) in enumerate(zip(segments, reviewed)):
            # Keep original text and voice_id (LLM should not change these)
            rev["text"] = orig["text"]
            rev["voice_id"] = orig["voice_id"]
            rev["role"] = orig["role"]
            # Validate emotion
            if rev.get("emotion") not in _VALID:
                rev["emotion"] = orig.get("emotion", "fluent")
            # Clamp parameters
            rev["speed"] = max(0.5, min(2.0, float(rev.get("speed", 1.0))))
            rev["pitch"] = max(-12, min(12, int(rev.get("pitch", 0))))
            rev["vol"] = max(0.1, min(10.0, float(rev.get("vol", 1.0))))

        logger.info("LLM voice director review completed successfully")
        return reviewed

    except Exception as e:
        logger.warning("LLM review failed, using original segments: %s", e)
        return None


def _vary_narration_params(segments: list[dict], narration_indices: list[int]):
    """Inject variation into narration segments based on text content analysis."""
    for i in narration_indices:
        seg = segments[i]
        text = seg.get("text", "")
        base_speed = seg.get("speed", 0.92)
        base_vol = seg.get("vol", 0.90)

        # Tense/dark atmosphere: slower, quieter
        if any(w in text for w in ("幽暗", "寂静", "黑暗", "阴森", "沉默", "死寂", "漆黑", "诡异", "凝视", "注视")):
            seg["speed"] = round(max(0.5, base_speed * 0.90), 2)
            seg["vol"] = round(max(0.1, base_vol * 0.85), 2)
            seg["emotion"] = "sad"
        # Action/sudden event: faster, louder
        elif any(w in text for w in ("猛地", "突然", "一声", "哐当", "砰", "冲", "扑", "抓住", "喊住", "追")):
            seg["speed"] = round(min(2.0, base_speed * 1.15), 2)
            seg["vol"] = round(min(10.0, base_vol * 1.20), 2)
            seg["emotion"] = "fluent"
        # Emotional/lyrical: slower, atmospheric
        elif any(w in text for w in ("月光", "风", "夜色", "摇曳", "飘", "静", "远处", "淡薄", "苍白")):
            seg["speed"] = round(max(0.5, base_speed * 0.88), 2)
            seg["vol"] = round(max(0.1, base_vol * 0.88), 2)
            seg["emotion"] = "fluent"
        # Suspense/reveal: slightly slower
        elif any(w in text for w in ("竟", "赫然", "居然", "果然", "原来", "不料", "没想到")):
            seg["speed"] = round(max(0.5, base_speed * 0.92), 2)
            seg["emotion"] = "surprised"
        # Short transition narration: keep brisk
        elif len(text) < 15:
            seg["speed"] = round(min(2.0, base_speed * 1.05), 2)

    logger.info("Narration variation applied to %d segments", len(narration_indices))


async def _enforce_emotion_diversity(tool_params: dict) -> dict:
    """Post-process batch_voice_over params: text enhance, emotion fix, LLM review.

    Appends `tool_params['voice_director']` with a diff summary so the frontend
    can show users what AI adjustments were made.
    """
    import re
    from collections import Counter

    segments = tool_params.get("segments", [])
    if len(segments) < 3:
        return tool_params

    # Snapshot the key fields before any mutation — used to diff at the end.
    snapshot_before = [
        {
            "role": s.get("role"),
            "emotion": s.get("emotion"),
            "speed": s.get("speed"),
            "pitch": s.get("pitch"),
            "vol": s.get("vol"),
        }
        for s in segments
    ]
    emotion_mix_before = dict(Counter(s.get("emotion") or "?" for s in segments))

    # Replace unsupported emotions
    _VALID_EMOTIONS = {"happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm", "fluent"}
    for seg in segments:
        emo = seg.get("emotion")
        if emo and emo not in _VALID_EMOTIONS:
            logger.warning("Replacing unsupported emotion '%s' with 'fluent'", emo)
            seg["emotion"] = "fluent"

    # --- Text-based parameter enhancement ---
    _enhance_text_params(segments)

    # Classify segments
    dialogue_indices = []
    narration_indices = []
    for i, seg in enumerate(segments):
        role = seg.get("role", "").strip()
        if role in _NARRATION_ROLES:
            narration_indices.append(i)
        else:
            dialogue_indices.append(i)

    # --- Fix emotion uniformity in dialogue ---
    if dialogue_indices:
        emotions = [segments[i].get("emotion") or "calm" for i in dialogue_indices]
        counter = Counter(emotions)
        most_common_emo, most_common_count = counter.most_common(1)[0]
        dominant_ratio = most_common_count / len(dialogue_indices)

        if dominant_ratio > 0.5:
            logger.warning(
                "Emotion diversity: %s dominates dialogue at %.0f%% (%d/%d). Auto-correcting.",
                most_common_emo, dominant_ratio * 100,
                most_common_count, len(dialogue_indices),
            )
            # Keep ~35% for the dominant emotion, redistribute rest to fluent (for calm) or calm (for fluent)
            fallback = "fluent" if most_common_emo == "calm" else "calm"
            target = max(1, int(len(dialogue_indices) * 0.35))
            seen = 0
            for i in dialogue_indices:
                emo = segments[i].get("emotion") or "calm"
                if emo == most_common_emo:
                    seen += 1
                    if seen > target:
                        segments[i]["emotion"] = fallback

    # --- Strip speech tags from narration segments ---
    speech_tag_re = re.compile(r'\([a-z-]+\)\s*')
    for i in narration_indices:
        text = segments[i].get("text", "")
        cleaned = speech_tag_re.sub("", text).strip()
        if cleaned != text.strip():
            logger.info("Stripped speech tags from narration: %s", text[:60])
            segments[i]["text"] = cleaned

    # --- Narration parameter variation (prevent identical template copying) ---
    if len(narration_indices) >= 3:
        _vary_narration_params(segments, narration_indices)

    # --- Log emotion summary for monitoring ---
    all_emotions = Counter(s.get("emotion", "?") for s in segments)
    logger.info("Emotion summary (pre-review): %s", dict(all_emotions))

    # --- LLM voice director review (only for 5+ segments) ---
    director_used = False
    director_reason: str | None = None
    if len(segments) >= 5 and llm.available:
        reviewed = await _llm_review_segments(segments)
        if reviewed is not None:
            segments = reviewed
            tool_params["segments"] = reviewed
            director_used = True
            all_emotions = Counter(s.get("emotion", "?") for s in reviewed)
            logger.info("Emotion summary (post-review): %s", dict(all_emotions))
        else:
            director_reason = "llm_review_failed"
            logger.warning("Voice director review returned None; using base segments")
    elif len(segments) < 5:
        director_reason = "fewer_than_5_segments"
    elif not llm.available:
        director_reason = "llm_unavailable"

    tool_params["segments"] = segments

    # Compute diff between pre- and post-enhancement state.
    diff = []
    for i, (before, after) in enumerate(zip(snapshot_before, segments)):
        changes = {
            k: {"from": before[k], "to": after.get(k)}
            for k in ("emotion", "speed", "pitch", "vol")
            if before[k] != after.get(k)
        }
        if changes:
            diff.append({"index": i, "role": after.get("role"), "changes": changes})

    tool_params["voice_director"] = {
        "director_used": director_used,
        "reason": director_reason,
        "changed_count": len(diff),
        "total": len(segments),
        "emotion_mix_before": emotion_mix_before,
        "emotion_mix_after": dict(Counter(s.get("emotion") or "?" for s in segments)),
        "diff": diff[:20],
    }
    return tool_params


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def create_session(db: AsyncSession, user: User, title: str | None = None) -> AgentSession:
    session = AgentSession(user_id=user.id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user: User) -> list[AgentSession]:
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.user_id == user.id)
        .order_by(AgentSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_id: str, user: User) -> AgentSession:
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == session_id, AgentSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


async def delete_session(db: AsyncSession, session_id: str, user: User):
    session = await get_session(db, session_id, user)
    await db.delete(session)
    await db.commit()


async def get_messages(db: AsyncSession, session_id: str) -> list[AgentMessage]:
    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at)
    )
    return list(result.scalars().all())


async def get_timeline(db: AsyncSession, session_id: str, user: User) -> list[dict]:
    await get_session(db, session_id, user)
    timeline = await build_timeline(db, session_id)
    for item in timeline:
        if item.get("type") == "tool_call":
            item["models"] = await get_tool_pricing(item["tool_name"], db, item.get("params"))
    return timeline


async def get_state_snapshot(db: AsyncSession, session_id: str, user: User) -> dict:
    session = await get_session(db, session_id, user)
    active_tool_call = await get_active_tool_call(db, session)
    snapshot = build_state_snapshot(session, active_tool_call)
    if snapshot["active_tool_call"]:
        snapshot["active_tool_call"]["models"] = await get_tool_pricing(
            active_tool_call.tool_name, db, active_tool_call.tool_params
        )
    return snapshot


async def upload_attachment(db: AsyncSession, session_id: str, file, user: User) -> dict:
    await get_session(db, session_id, user)
    attachment = await save_attachment(db, user, session_id, file)
    return {
        "id": attachment.id,
        "session_id": attachment.session_id,
        "kind": attachment.kind.value,
        "original_name": attachment.original_name,
        "mime_type": attachment.mime_type,
        "extracted_text": attachment.extracted_text,
        "created_at": attachment.created_at.isoformat(),
    }


async def cancel_tool(session_id: str, tool_call_id: str, db: AsyncSession, user: User) -> dict:
    session = await get_session(db, session_id, user)
    tool_call = await get_tool_call(db, session_id, tool_call_id)
    if tool_call is None:
        raise HTTPException(status_code=404, detail="找不到对应的工具调用")
    await cancel_tool_call_record(db, session, tool_call)
    snapshot = build_state_snapshot(session, None)
    return {
        "success": True,
        "tool_call": {
            **serialize_tool_call(tool_call),
            "models": await get_tool_pricing(tool_call.tool_name, db, tool_call.tool_params),
        },
        "state": snapshot,
    }


# ---------------------------------------------------------------------------
# Convert DB messages to OpenAI format
# ---------------------------------------------------------------------------

def _msg_to_openai(msg: AgentMessage) -> dict:
    """Convert a stored AgentMessage to OpenAI chat format."""
    d: dict = {"role": msg.role}
    if msg.content:
        d["content"] = msg.content
    if msg.tool_calls:
        d["tool_calls"] = msg.tool_calls
        if not msg.content:
            d["content"] = None
    if msg.role == MessageRole.tool:
        d["tool_call_id"] = msg.tool_call_id or ""
        d["content"] = msg.content or ""
    return d


async def _selected_attachments(db: AsyncSession, session_id: str, user: User, attachment_ids: list[str]) -> list:
    attachments = await list_session_attachments(db, session_id, user)
    if not attachment_ids:
        return attachments
    selected_ids = set(attachment_ids)
    return [attachment for attachment in attachments if attachment.id in selected_ids]


async def _emit_state_event(session: AgentSession, db: AsyncSession) -> dict:
    active_tool_call = await get_active_tool_call(db, session)
    snapshot = build_state_snapshot(session, active_tool_call)
    if active_tool_call:
        snapshot["active_tool_call"]["models"] = await get_tool_pricing(
            active_tool_call.tool_name, db, active_tool_call.tool_params
        )
    return {"event": "state", "data": snapshot}


async def _persist_tool_message(db: AsyncSession, session_id: str, tool_call_id: str, tool_name: str, result: dict) -> AgentMessage:
    tool_message = AgentMessage(
        session_id=session_id,
        role=MessageRole.tool,
        content=json.dumps(result, ensure_ascii=False, default=str),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
    )
    db.add(tool_message)
    await db.flush()
    return tool_message


async def _handle_tool_calls(
    session: AgentSession,
    assistant_message: AgentMessage,
    raw_tool_calls: list[dict] | None,
    db: AsyncSession,
    user: User,
) -> AsyncGenerator[dict, None]:
    normalized = normalize_tool_calls(raw_tool_calls)
    actionable, warnings = select_actionable_tool_calls(normalized)
    for warning in warnings:
        yield {"event": "warning", "data": {"message": warning}}

    auto_executed = False
    for raw_tool_call in actionable:
        tool_call_id = raw_tool_call.get("id", str(uuid.uuid4()))
        function = raw_tool_call.get("function", {})
        tool_name = function.get("name", "")
        tool_def = get_tool(tool_name)
        if tool_def is None:
            yield {"event": "error", "data": {"message": f"未知工具: {tool_name}"}}
            continue

        try:
            tool_params = json.loads(function.get("arguments", "{}"))
        except json.JSONDecodeError:
            tool_params = {}
        if tool_name == "batch_voice_over":
            tool_params = await _enforce_emotion_diversity(tool_params)
            try:
                voices = (await voice_service.list_voices(voice_type="all")).get("voices", [])
            except Exception as exc:
                logger.warning("Failed to fetch voices for batch voice selection: %s", exc)
                voices = []
            tool_params = enrich_batch_voice_over_params(tool_params, voices)
            voice_selection = tool_params.get("voice_selection") or {}
            voice_selection, memory_hits = await apply_memory_to_selection(
                db, user.id, voice_selection, voices,
            )
            tool_params["voice_selection"] = voice_selection
            tool_params["segments"] = apply_role_voice_selection(
                tool_params.get("segments", []), voice_selection,
            )
            if memory_hits:
                logger.info("Voice memory applied for roles: %s", list(memory_hits.keys()))

        tool_call = await create_tool_call_record(
            db, session, assistant_message, tool_name, tool_params, tool_call_id
        )
        models = await get_tool_pricing(tool_name, db, tool_params)
        payload = {**serialize_tool_call(tool_call), "models": models}

        if tool_def.require_confirmation:
            mark_session_status(session, AgentSessionStatus.awaiting_confirmation, tool_call.id)
            await db.flush()
            yield await _emit_state_event(session, db)
            yield {"event": "tool_call_created", "data": payload}
            yield {"event": "tool_call", "data": payload}
            continue

        yield {"event": "tool_call_created", "data": payload}
        yield {"event": "tool_call_updated", "data": {**payload, "status": AgentToolCallStatus.executing.value}}
        result = await execute_tool_call(
            db=db,
            user=user,
            session=session,
            tool_call=tool_call,
            tool_def=tool_def,
            client_request_id=f"auto-{uuid.uuid4()}",
        )
        await _persist_tool_message(db, session.id, tool_call.id, tool_name, result["result"])
        await db.refresh(tool_call)
        yield await _emit_state_event(session, db)
        yield {"event": "tool_call_updated", "data": {**serialize_tool_call(tool_call), "models": models}}
        yield {
            "event": "tool_result",
            "data": {
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "result": result["result"],
                "credits_cost": tool_call.credits_cost,
            },
        }
        auto_executed = True

    if auto_executed and session.status != AgentSessionStatus.awaiting_confirmation:
        async for event in _continue_after_tools(session.id, db, user):
            yield event


# ---------------------------------------------------------------------------
# Core chat flow
# ---------------------------------------------------------------------------

async def chat(
    session_id: str,
    user_message: str,
    db: AsyncSession,
    user: User,
    attachment_ids: list[str] | None = None,
) -> AsyncGenerator[dict, None]:
    """Process a user message. Yields SSE event dicts."""

    if not llm.available:
        yield {"event": "error", "data": {"message": "AI 助手未配置，请联系管理员设置 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL"}}
        return

    session = await get_session(db, session_id, user)
    if session.status in {AgentSessionStatus.cancelled, AgentSessionStatus.completed} and not session.active_tool_call_id:
        mark_session_status(session, AgentSessionStatus.idle, None)

    # Save user message
    user_msg = AgentMessage(session_id=session_id, role=MessageRole.user, content=user_message)
    db.add(user_msg)
    await db.flush()

    # Update session title from first message
    if not session.title:
        session.title = user_message[:50]

    # Build messages for LLM
    attachments = await _selected_attachments(db, session_id, user, attachment_ids or [])
    history = await get_messages(db, session_id)
    history_openai = [_msg_to_openai(m) for m in history]
    active_tool_call = await get_active_tool_call(db, session)
    system_prompt, matched_skills = await build_system_prompt(
        user, db,
        session=session,
        user_message=user_message,
        conversation_context=history_openai,
        attachments=attachments,
        active_tool_call=active_tool_call,
    )
    openai_messages = [{"role": "system", "content": system_prompt}]
    openai_messages.extend(history_openai)

    # Notify frontend about matched skills
    if matched_skills:
        yield {"event": "skills", "data": {"skills": matched_skills}}
    yield await _emit_state_event(session, db)

    # Call LLM with streaming
    full_text = ""
    tool_calls = None

    try:
        async for delta in llm.chat_stream(openai_messages, tools=get_openai_tools()):
            if delta["type"] == "text":
                full_text += delta["content"]
                yield {"event": "assistant_delta", "data": {"content": delta["content"]}}
                yield {"event": "text", "data": {"content": delta["content"]}}
            elif delta["type"] == "tool_calls":
                tool_calls = delta["tool_calls"]
            elif delta["type"] == "done":
                pass
    except Exception as e:
        detail = _format_llm_error(e)
        logger.error("LLM 流式调用失败: %s\n%s", detail, traceback.format_exc())
        yield {"event": "error", "data": {"message": f"LLM 调用失败: {detail}"}}
        await db.commit()
        return

    # Save assistant message
    assistant_msg = AgentMessage(
        session_id=session_id,
        role=MessageRole.assistant,
        content=full_text or None,
        tool_calls=tool_calls,
    )
    db.add(assistant_msg)
    await db.flush()

    if tool_calls:
        async for event in _handle_tool_calls(session, assistant_msg, tool_calls, db, user):
            yield event

    session.updated_at = datetime.utcnow()
    await db.commit()
    yield {"event": "done", "data": {}}


# ---------------------------------------------------------------------------
# Tool confirmation + execution
# ---------------------------------------------------------------------------

async def confirm_tool(
    session_id: str,
    tool_call_id: str,
    selected_model: str | None,
    db: AsyncSession,
    user: User,
    client_request_id: str,
    param_overrides: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """Execute a confirmed tool call with billing."""

    session = await get_session(db, session_id, user)
    tool_call = await get_tool_call(db, session_id, tool_call_id)
    if tool_call is None:
        yield {"event": "error", "data": {"message": "找不到对应的工具调用"}}
        return

    tool_def = get_tool(tool_call.tool_name)
    if not tool_def:
        yield {"event": "error", "data": {"message": f"未知工具: {tool_call.tool_name}"}}
        return

    models = await get_tool_pricing(tool_call.tool_name, db, tool_call.tool_params)
    yield {"event": "tool_call_updated", "data": {**serialize_tool_call(tool_call), "models": models, "status": AgentToolCallStatus.executing.value}}
    result = await execute_tool_call(
        db=db,
        user=user,
        session=session,
        tool_call=tool_call,
        tool_def=tool_def,
        client_request_id=client_request_id,
        selected_model=selected_model,
        param_overrides=param_overrides,
    )
    await db.refresh(tool_call)
    await _persist_tool_message(db, session_id, tool_call.id, tool_call.tool_name, result["result"])
    yield await _emit_state_event(session, db)
    yield {"event": "tool_call_updated", "data": {**serialize_tool_call(tool_call), "models": models}}
    yield {
        "event": "tool_result",
        "data": {
            "tool_call_id": tool_call.id,
            "name": tool_call.tool_name,
            "result": result["result"],
            "credits_cost": tool_call.credits_cost,
        },
    }
    yield {
        "event": "balance_updated",
        "data": {"credits": user.credits, "free_credits": user.free_credits},
    }
    yield {
        "event": "balance",
        "data": {"credits": user.credits, "free_credits": user.free_credits},
    }

    if result["status"] == "succeeded":
        async for event in _continue_after_tools(session_id, db, user):
            yield event

    session.updated_at = datetime.utcnow()
    await db.commit()
    yield {"event": "done", "data": {}}


# ---------------------------------------------------------------------------
# Continue conversation after tool results
# ---------------------------------------------------------------------------

async def _continue_after_tools(
    session_id: str,
    db: AsyncSession,
    user: User,
) -> AsyncGenerator[dict, None]:
    """Re-invoke LLM with updated message history (including tool results)."""

    session = await get_session(db, session_id, user)
    attachments = await list_session_attachments(db, session_id, user)
    history = await get_messages(db, session_id)
    history_openai = [_msg_to_openai(m) for m in history]

    # Find the most recent user message for skill matching
    last_user_msg = ""
    for msg in reversed(history):
        if msg.role == MessageRole.user and msg.content:
            last_user_msg = msg.content
            break

    active_tool_call = await get_active_tool_call(db, session)
    system_prompt, matched_skills = await build_system_prompt(
        user, db,
        session=session,
        user_message=last_user_msg,
        conversation_context=history_openai,
        attachments=attachments,
        active_tool_call=active_tool_call,
    )
    openai_messages = [{"role": "system", "content": system_prompt}]
    openai_messages.extend(history_openai)

    full_text = ""
    tool_calls = None

    try:
        async for delta in llm.chat_stream(openai_messages, tools=get_openai_tools()):
            if delta["type"] == "text":
                full_text += delta["content"]
                yield {"event": "assistant_delta", "data": {"content": delta["content"]}}
                yield {"event": "text", "data": {"content": delta["content"]}}
            elif delta["type"] == "tool_calls":
                tool_calls = delta["tool_calls"]
    except Exception as e:
        detail = _format_llm_error(e)
        logger.error("LLM 后续流式调用失败: %s\n%s", detail, traceback.format_exc())
        yield {"event": "error", "data": {"message": f"LLM 调用失败: {detail}"}}
        return

    # Save assistant follow-up
    if full_text or tool_calls:
        follow_msg = AgentMessage(
            session_id=session_id,
            role=MessageRole.assistant,
            content=full_text or None,
            tool_calls=tool_calls,
        )
        db.add(follow_msg)
        await db.flush()

    if tool_calls:
        async for event in _handle_tool_calls(session, follow_msg, tool_calls, db, user):
            yield event
