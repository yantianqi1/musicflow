"""Agent tool definitions.

Each tool wraps an existing MusicFlow service as an OpenAI function-calling tool.
The TOOL_REGISTRY maps tool names to their schema, pricing metadata, and executor.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.services import music_service, speech_service, voice_service
from backend.services.agent_attachments import get_attachment, read_attachment_bytes
from backend.services.billing_service import estimate_cost, get_pricing_rule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definition dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentToolDef:
    name: str
    openai_schema: dict                          # passed to LLM as tool definition
    service_type: str | None                     # for billing lookup; None = free
    available_models: list[dict] = field(default_factory=list)  # [{id, name, description}]
    require_confirmation: bool = True            # False for free/query tools
    executor: Callable[..., Awaitable[dict]] = None  # async (params, db, user) -> dict


TOOL_REGISTRY: dict[str, AgentToolDef] = {}


def _register(tool: AgentToolDef):
    TOOL_REGISTRY[tool.name] = tool


def get_openai_tools() -> list[dict]:
    """Return all tool schemas in OpenAI function-calling format."""
    return [t.openai_schema for t in TOOL_REGISTRY.values()]


def get_tool(name: str) -> AgentToolDef | None:
    return TOOL_REGISTRY.get(name)


# ---------------------------------------------------------------------------
# Helper: build pricing summary for a tool (queried at runtime from DB)
# ---------------------------------------------------------------------------

def _derive_billable_chars(tool_params: dict | None) -> int:
    """Match billing_service._count_billable_chars for pricing preview."""
    if not tool_params:
        return 0
    if "segments" in tool_params:
        return sum(len(item.get("text", "")) for item in tool_params.get("segments", []) or [])
    return len(tool_params.get("text", "") or "")


async def get_tool_pricing(name: str, db: AsyncSession, tool_params: dict | None = None) -> list[dict]:
    """Return available models with live pricing for a given tool.

    When ``tool_params`` is provided, the ``cost`` field reflects the actual
    predicted credits for this specific call (based on char_count for
    per_10k_chars billing), and ``unit_cost`` carries the rate card value so
    the UI can still display '单价 X/万字符'.
    """
    tool = TOOL_REGISTRY.get(name)
    if not tool or not tool.service_type:
        return []
    char_count = _derive_billable_chars(tool_params)
    results = []
    if tool.available_models:
        for m in tool.available_models:
            rule = await get_pricing_rule(db, tool.service_type, m.get("id"))
            unit_cost = rule.credits_per_use
            estimated = await estimate_cost(db, tool.service_type, m.get("id"), char_count)
            results.append({
                **m,
                "cost": estimated,
                "unit_cost": unit_cost,
                "billing_unit": rule.billing_unit,
                "char_count": char_count,
            })
    else:
        rule = await get_pricing_rule(db, tool.service_type)
        estimated = await estimate_cost(db, tool.service_type, None, char_count)
        results.append({
            "id": None,
            "name": tool.name,
            "cost": estimated,
            "unit_cost": rule.credits_per_use,
            "billing_unit": rule.billing_unit,
            "unit": "积分/次",
            "char_count": char_count,
        })
    return results


# ===================================================================
# 1. generate_lyrics
# ===================================================================

async def _exec_generate_lyrics(params: dict, db: AsyncSession, user: User) -> dict:
    return await music_service.generate_lyrics(
        prompt=params.get("prompt", ""),
        mode=params.get("mode", "write_full_song"),
        lyrics=params.get("lyrics"),
        title=params.get("title"),
        target_duration=params.get("target_duration"),
    )

_register(AgentToolDef(
    name="generate_lyrics",
    service_type="lyrics",
    available_models=[],
    require_confirmation=True,
    executor=_exec_generate_lyrics,
    openai_schema={
        "type": "function",
        "function": {
            "name": "generate_lyrics",
            "description": "生成歌词。根据主题/风格描述自动创作完整歌词，也可对已有歌词进行编辑续写。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "歌曲主题和风格描述，如'一首关于夏天的欢快流行歌曲'",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write_full_song", "edit"],
                        "description": "write_full_song=创作完整歌词, edit=编辑已有歌词。默认 write_full_song",
                    },
                    "lyrics": {
                        "type": "string",
                        "description": "已有歌词（mode=edit 时使用）",
                    },
                    "title": {
                        "type": "string",
                        "description": "指定歌曲标题（可选）",
                    },
                    "target_duration": {
                        "type": "string",
                        "enum": ["short", "medium", "standard", "long"],
                        "description": "目标时长: short=20-40秒, medium=1-2分钟, standard=2-3分钟(默认), long=3-4分钟。系统会根据时长自动控制歌词结构和段落数",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
))


# ===================================================================
# 2. generate_music
# ===================================================================

async def _exec_generate_music(params: dict, db: AsyncSession, user: User) -> dict:
    return await music_service.generate_music(
        model=params["model"],
        prompt=params.get("prompt", ""),
        lyrics=params.get("lyrics"),
        sample_rate=params.get("sample_rate", 44100),
        bitrate=params.get("bitrate", 256000),
        audio_format=params.get("audio_format", "mp3"),
        is_instrumental=params.get("is_instrumental", False),
        lyrics_optimizer=params.get("lyrics_optimizer", False),
        target_duration=params.get("target_duration"),
        aigc_watermark=params.get("aigc_watermark"),
    )

_register(AgentToolDef(
    name="generate_music",
    service_type="music",
    available_models=[
        {"id": "music-2.6", "name": "Music-2.6", "description": "高质量音乐生成", "unit": "积分/首"},
    ],
    require_confirmation=True,
    executor=_exec_generate_music,
    openai_schema={
        "type": "function",
        "function": {
            "name": "generate_music",
            "description": "生成音乐。可根据文字描述和/或歌词生成完整音乐。支持纯器乐模式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "enum": ["music-2.6"],
                        "description": "音乐模型",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "音乐风格描述，如'伤感 抒情 钢琴 慢节奏'",
                    },
                    "lyrics": {
                        "type": "string",
                        "description": "歌词（可选，支持结构标签如[Verse][Chorus]）",
                    },
                    "is_instrumental": {
                        "type": "boolean",
                        "description": "是否生成纯器乐（无人声）。默认 false",
                    },
                    "lyrics_optimizer": {
                        "type": "boolean",
                        "description": "是否自动优化歌词。默认 false",
                    },
                    "sample_rate": {"type": "integer", "description": "采样率，默认 44100"},
                    "bitrate": {"type": "integer", "description": "比特率，默认 256000"},
                    "audio_format": {"type": "string", "enum": ["mp3", "wav", "pcm"], "description": "音频格式，默认 mp3"},
                    "target_duration": {
                        "type": "string",
                        "enum": ["short", "medium", "standard", "long"],
                        "description": "目标时长: short=20-40秒, medium=1-2分钟, standard=2-3分钟(默认), long=3-4分钟。对纯器乐(is_instrumental=true)会在prompt中添加时长提示",
                    },
                    "aigc_watermark": {
                        "type": "boolean",
                        "description": "是否添加AI生成内容水印，默认不添加",
                    },
                },
                "required": ["model", "prompt"],
            },
        },
    },
))


# ===================================================================
# 3. generate_cover
# ===================================================================

async def _exec_generate_cover(params: dict, db: AsyncSession, user: User) -> dict:
    audio_base64 = params.get("audio_base64")
    attachment_id = params.get("attachment_id")
    if attachment_id and not params.get("audio_url") and not audio_base64:
        attachment_bytes = await read_attachment_bytes(db, attachment_id, user)
        audio_base64 = base64.b64encode(attachment_bytes).decode("utf-8")
    return await music_service.generate_cover(
        model=params["model"],
        prompt=params.get("prompt", ""),
        audio_url=params.get("audio_url"),
        audio_base64=audio_base64,
        lyrics=params.get("lyrics"),
        sample_rate=params.get("sample_rate", 44100),
        bitrate=params.get("bitrate", 256000),
        audio_format=params.get("audio_format", "mp3"),
        aigc_watermark=params.get("aigc_watermark"),
    )

_register(AgentToolDef(
    name="generate_cover",
    service_type="music_cover",
    available_models=[
        {"id": "music-cover", "name": "Music-Cover", "description": "高质量翻唱生成", "unit": "积分/首"},
    ],
    require_confirmation=True,
    executor=_exec_generate_cover,
    openai_schema={
        "type": "function",
        "function": {
            "name": "generate_cover",
            "description": "生成翻唱。根据参考音频和风格描述生成翻唱版本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "enum": ["music-cover"],
                        "description": "翻唱模型",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "翻唱风格描述",
                    },
                    "audio_url": {
                        "type": "string",
                        "description": "参考音频URL（与audio_base64二选一）",
                    },
                    "audio_base64": {
                        "type": "string",
                        "description": "参考音频的Base64编码（与audio_url二选一）",
                    },
                    "attachment_id": {
                        "type": "string",
                        "description": "已上传到 AI 助手会话的本地音频附件 ID（与 audio_url/audio_base64 二选一）",
                    },
                    "lyrics": {
                        "type": "string",
                        "description": "歌词（可选）",
                    },
                    "sample_rate": {"type": "integer", "description": "采样率，默认 44100"},
                    "bitrate": {"type": "integer", "description": "比特率，默认 256000"},
                    "audio_format": {"type": "string", "enum": ["mp3", "wav", "pcm"], "description": "音频格式，默认 mp3"},
                    "aigc_watermark": {
                        "type": "boolean",
                        "description": "是否添加AI生成内容水印",
                    },
                },
                "required": ["model", "prompt"],
            },
        },
    },
))


# ===================================================================
# 4. text_to_speech (sync)
# ===================================================================

async def _exec_text_to_speech(params: dict, db: AsyncSession, user: User) -> dict:
    return await speech_service.sync_speech(
        model=params["model"],
        text=params["text"],
        voice_id=params.get("voice_id", "male-qn-qingse"),
        speed=params.get("speed", 1.0),
        vol=params.get("vol", 1.0),
        pitch=params.get("pitch", 0),
        emotion=params.get("emotion", "auto"),
        sample_rate=params.get("sample_rate", 32000),
        bitrate=params.get("bitrate", 128000),
        audio_format=params.get("audio_format", "mp3"),
        channel=params.get("channel", 1),
        language_boost=params.get("language_boost", "auto"),
        aigc_watermark=params.get("aigc_watermark"),
        subtitle_enable=params.get("subtitle_enable"),
        text_normalization=params.get("text_normalization"),
        latex_read=params.get("latex_read"),
        force_cbr=params.get("force_cbr"),
    )

_register(AgentToolDef(
    name="text_to_speech",
    service_type="speech_sync",
    available_models=[
        {"id": "speech-2.8-hd", "name": "Speech-2.8-HD", "description": "高保真·广播级音质，情感细腻", "unit": "积分/万字符"},
        {"id": "speech-2.8-turbo", "name": "Speech-2.8-Turbo", "description": "极速低价·2-3x速度，日常够用", "unit": "积分/万字符"},
    ],
    require_confirmation=True,
    executor=_exec_text_to_speech,
    openai_schema={
        "type": "function",
        "function": {
            "name": "text_to_speech",
            "description": "文字转语音（同步，适合1万字以内）。支持多种音色、情感、语速控制。",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "enum": ["speech-2.8-hd", "speech-2.8-turbo"],
                        "description": "语音模型：hd=高保真贵，turbo=速度快便宜约四成",
                    },
                    "text": {
                        "type": "string",
                        "description": "要转为语音的文字内容（最多1万字符）",
                    },
                    "voice_id": {
                        "type": "string",
                        "description": "音色ID，如 male-qn-qingse, female-shaonv 等。可先用 list_voices 查询可用音色",
                    },
                    "speed": {
                        "type": "number",
                        "description": "语速，0.5~2.0，默认1.0",
                    },
                    "emotion": {
                        "type": "string",
                        "enum": ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "fluent", "calm"],
                        "description": "情感: happy/sad/angry/fearful/disgusted/surprised/fluent(生动)/calm(平静)，不设则自动判断",
                    },
                    "pitch": {
                        "type": "integer",
                        "description": "音调，-12~12，默认0",
                    },
                    "language_boost": {
                        "type": "string",
                        "description": "语言增强，如 Chinese, English, Japanese 等，默认 auto",
                    },
                    "vol": {"type": "number", "description": "音量 0.1~10.0，默认 1.0"},
                    "sample_rate": {"type": "integer", "description": "采样率，默认 32000"},
                    "bitrate": {"type": "integer", "description": "比特率，默认 128000"},
                    "audio_format": {
                        "type": "string",
                        "enum": ["mp3", "wav", "pcm", "flac"],
                        "description": "音频格式，默认 mp3",
                    },
                    "channel": {
                        "type": "integer",
                        "description": "声道数: 1=单声道, 2=立体声。默认 1",
                    },
                    "aigc_watermark": {
                        "type": "boolean",
                        "description": "是否添加AI生成内容水印",
                    },
                    "subtitle_enable": {
                        "type": "boolean",
                        "description": "是否返回字幕/时间戳信息",
                    },
                    "text_normalization": {
                        "type": "boolean",
                        "description": "是否启用文本规范化（数字、日期等朗读规则）",
                    },
                    "latex_read": {
                        "type": "boolean",
                        "description": "是否启用LaTeX公式朗读（仅中文）",
                    },
                    "force_cbr": {
                        "type": "boolean",
                        "description": "是否强制使用固定比特率编码",
                    },
                },
                "required": ["model", "text"],
            },
        },
    },
))


# ===================================================================
# 5. long_text_to_speech (async)
# ===================================================================

async def _exec_long_text_to_speech(params: dict, db: AsyncSession, user: User) -> dict:
    text_file_id = params.get("text_file_id")
    attachment_id = params.get("attachment_id")
    if text_file_id is None and attachment_id:
        attachment = await get_attachment(db, attachment_id, user)
        attachment_bytes = await read_attachment_bytes(db, attachment_id, user)
        text_file_id = await voice_service.upload_file(
            attachment_bytes,
            attachment.original_name,
            "file_extract",
        )
    return await speech_service.async_speech(
        model=params["model"],
        text=params.get("text"),
        voice_id=params.get("voice_id", "audiobook_male_1"),
        speed=params.get("speed", 1.0),
        vol=params.get("vol", 1.0),
        pitch=params.get("pitch", 0),
        emotion=params.get("emotion", "auto"),
        sample_rate=params.get("sample_rate", 32000),
        bitrate=params.get("bitrate", 128000),
        audio_format=params.get("audio_format", "mp3"),
        channel=params.get("channel", 1),
        language_boost=params.get("language_boost", "auto"),
        text_file_id=text_file_id,
    )

_register(AgentToolDef(
    name="long_text_to_speech",
    service_type="speech_async",
    available_models=[
        {"id": "speech-2.8-hd", "name": "Speech-2.8-HD", "description": "高保真·广播级音质", "unit": "积分/万字符"},
        {"id": "speech-2.8-turbo", "name": "Speech-2.8-Turbo", "description": "极速低价·适合长文批量合成", "unit": "积分/万字符"},
    ],
    require_confirmation=True,
    executor=_exec_long_text_to_speech,
    openai_schema={
        "type": "function",
        "function": {
            "name": "long_text_to_speech",
            "description": "长文本语音合成（异步，适合超过1万字符的大段文本）。返回任务ID，需用 query_task_status 查询进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "enum": ["speech-2.8-hd", "speech-2.8-turbo"],
                        "description": "语音模型：hd=高保真贵，turbo=速度快便宜约四成",
                    },
                    "text": {
                        "type": "string",
                        "description": "要转为语音的文字内容（与text_file_id二选一）",
                    },
                    "text_file_id": {
                        "type": "integer",
                        "description": "已上传的文本文件ID（与text二选一，适合超大文本）。需先用upload_file上传文本文件",
                    },
                    "attachment_id": {
                        "type": "string",
                        "description": "已上传到 AI 助手会话的文本附件 ID。后端会自动上传并换成 text_file_id",
                    },
                    "voice_id": {
                        "type": "string",
                        "description": "音色ID",
                    },
                    "speed": {"type": "number", "description": "语速 0.5~2.0"},
                    "emotion": {"type": "string", "description": "情感: happy/sad/angry/fearful/disgusted/surprised/fluent(生动)/calm(平静)"},
                    "channel": {
                        "type": "integer",
                        "description": "声道数: 1=单声道, 2=立体声。默认 1",
                    },
                    "audio_format": {
                        "type": "string",
                        "enum": ["mp3", "wav", "pcm", "flac"],
                        "description": "音频格式，默认 mp3",
                    },
                },
                "required": ["model"],
            },
        },
    },
))


# ===================================================================
# 6. clone_voice
# ===================================================================

async def _exec_clone_voice(params: dict, db: AsyncSession, user: User) -> dict:
    file_id = params.get("file_id")
    attachment_id = params.get("attachment_id")
    if file_id is None and attachment_id:
        attachment = await get_attachment(db, attachment_id, user)
        attachment_bytes = await read_attachment_bytes(db, attachment_id, user)
        file_id = await voice_service.upload_file(attachment_bytes, attachment.original_name, "voice_clone")

    prompt_audio_file_id = params.get("prompt_audio_file_id")
    prompt_attachment_id = params.get("prompt_attachment_id")
    if prompt_audio_file_id is None and prompt_attachment_id:
        prompt_attachment = await get_attachment(db, prompt_attachment_id, user)
        prompt_attachment_bytes = await read_attachment_bytes(db, prompt_attachment_id, user)
        prompt_audio_file_id = await voice_service.upload_file(
            prompt_attachment_bytes,
            prompt_attachment.original_name,
            "voice_clone",
        )
    return await voice_service.clone_voice(
        file_id=file_id,
        voice_id=params["voice_id"],
        text=params.get("text", "你好，这是我的声音克隆测试。"),
        model=params.get("model", "speech-2.8-hd"),
        prompt_audio_file_id=prompt_audio_file_id,
        prompt_text=params.get("prompt_text"),
    )

_register(AgentToolDef(
    name="clone_voice",
    service_type="voice_clone",
    available_models=[],
    require_confirmation=True,
    executor=_exec_clone_voice,
    openai_schema={
        "type": "function",
        "function": {
            "name": "clone_voice",
            "description": "克隆声音。需要先上传音频文件获取 file_id。克隆后可在语音合成中使用该音色。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "已上传的音频文件ID（需先用 upload_file 上传音频）",
                    },
                    "attachment_id": {
                        "type": "string",
                        "description": "已上传到 AI 助手会话的本地音频附件 ID。后端会自动上传并换成 file_id",
                    },
                    "voice_id": {
                        "type": "string",
                        "description": "自定义音色ID标识",
                    },
                    "text": {
                        "type": "string",
                        "description": "预览文本，用于生成克隆后的试听音频",
                    },
                    "prompt_audio_file_id": {
                        "type": "integer",
                        "description": "提示音频文件ID（可选）。用于指导克隆方向，需先用 upload_file 上传",
                    },
                    "prompt_attachment_id": {
                        "type": "string",
                        "description": "已上传到 AI 助手会话的提示音频附件 ID。后端会自动上传并换成 prompt_audio_file_id",
                    },
                    "prompt_text": {
                        "type": "string",
                        "description": "提示音频对应的文字内容（可选）。提供 prompt_audio_file_id 时建议同时提供",
                    },
                },
                "required": ["voice_id"],
            },
        },
    },
))


# ===================================================================
# 7. design_voice
# ===================================================================

async def _exec_design_voice(params: dict, db: AsyncSession, user: User) -> dict:
    return await voice_service.design_voice(
        prompt=params["prompt"],
        preview_text=params.get("preview_text", "你好，这是AI设计的声音。"),
        voice_id=params.get("voice_id"),
        aigc_watermark=params.get("aigc_watermark"),
    )

_register(AgentToolDef(
    name="design_voice",
    service_type="voice_design",
    available_models=[],
    require_confirmation=True,
    executor=_exec_design_voice,
    openai_schema={
        "type": "function",
        "function": {
            "name": "design_voice",
            "description": "AI设计声音。用自然语言描述想要的声音特征，AI 生成对应音色。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "声音特征描述，如'成熟稳重的男性声音，低沉有磁性，语速适中'",
                    },
                    "preview_text": {
                        "type": "string",
                        "description": "试听文本（最多500字）",
                    },
                    "aigc_watermark": {
                        "type": "boolean",
                        "description": "是否添加AI生成内容水印",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
))


# ===================================================================
# 8. list_voices (free, no confirmation)
# ===================================================================

async def _exec_list_voices(params: dict, db: AsyncSession, user: User) -> dict:
    try:
        return await voice_service.list_voices(voice_type=params.get("voice_type", "all"))
    except Exception:
        logger.exception("list_voices failed")
        raise

_register(AgentToolDef(
    name="list_voices",
    service_type=None,
    available_models=[],
    require_confirmation=False,
    executor=_exec_list_voices,
    openai_schema={
        "type": "function",
        "function": {
            "name": "list_voices",
            "description": "查询可用的声音列表（免费）。返回系统预置声音和用户自定义声音。",
            "parameters": {
                "type": "object",
                "properties": {
                    "voice_type": {
                        "type": "string",
                        "enum": ["all", "system", "voice_cloning", "voice_generation"],
                        "description": "声音类型过滤，默认 all",
                    },
                },
            },
        },
    },
))


# ===================================================================
# 8.2 list_voice_memory (free, no confirmation)
# ===================================================================

async def _exec_list_voice_memory(params: dict, db: AsyncSession, user: User) -> dict:
    from backend.services.agent_voice_memory import load_memory_map, normalize_role_key

    requested_roles = params.get("roles") or []
    memory_map = await load_memory_map(db, user.id)

    try:
        voices_payload = await voice_service.list_voices(voice_type="all")
        voices = voices_payload.get("voices", []) if isinstance(voices_payload, dict) else []
    except Exception:
        logger.exception("list_voice_memory: catalog lookup failed; continuing without voice_name")
        voices = []
    catalog_by_id = {v.get("voice_id"): v for v in voices if v.get("voice_id")}

    def _serialize(entry: dict, role_display: str) -> dict:
        voice_id = entry["voice_id"]
        catalog_entry = catalog_by_id.get(voice_id)
        return {
            "role": role_display,
            "voice_id": voice_id,
            "voice_name": (catalog_entry or {}).get("voice_name") or voice_id,
            "source": entry.get("source"),
            "usage_count": entry.get("usage_count"),
        }

    if requested_roles:
        matched, missing = [], []
        for role_name in requested_roles:
            key = normalize_role_key(role_name)
            if key and key in memory_map:
                matched.append(_serialize(memory_map[key], role_name))
            else:
                missing.append(role_name)
        return {
            "total_memory_entries": len(memory_map),
            "matched": matched,
            "missing": missing,
            "hint": (
                "matched 中的角色请直接沿用 voice_id；missing 中的角色按常规流程挑选音色。"
                if matched
                else "所查询角色均无历史记忆，请按常规流程挑选音色。"
            ),
        }

    items = [
        _serialize(entry, entry.get("role_display") or role_key)
        for role_key, entry in memory_map.items()
    ]
    return {
        "total_memory_entries": len(items),
        "items": items,
        "hint": "如需查询特定角色，可传 roles 参数过滤。",
    }


_register(AgentToolDef(
    name="list_voice_memory",
    service_type=None,
    available_models=[],
    require_confirmation=False,
    executor=_exec_list_voice_memory,
    openai_schema={
        "type": "function",
        "function": {
            "name": "list_voice_memory",
            "description": (
                "查询当前用户的角色音色记忆（免费，无需确认）。"
                "在 batch_voice_over 的第一步识别出角色后，必须先调用本工具以沿用历史音色。"
                "返回 matched（已有记忆，直接用其 voice_id）与 missing（需要重新挑选音色）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要查询的角色名数组；不传则返回用户全部记忆。支持中文/英文别名（旁白/叙述者/narrator 会自动归一）。",
                    },
                },
                "required": [],
            },
        },
    },
))


# ===================================================================
# 8.5 batch_voice_over (novel/drama multi-character TTS)
# ===================================================================

async def _exec_batch_voice_over(params: dict, db: AsyncSession, user: User) -> dict:
    return await speech_service.batch_voice_over(
        segments=params["segments"],
        model=params.get("model", "speech-2.8-hd"),
        speed=params.get("speed", 1.0),
    )

_register(AgentToolDef(
    name="batch_voice_over",
    service_type="speech_sync",
    available_models=[
        {"id": "speech-2.8-hd", "name": "Speech-2.8-HD", "description": "高保真·角色情感层次丰富", "unit": "积分/万字符"},
        {"id": "speech-2.8-turbo", "name": "Speech-2.8-Turbo", "description": "极速低价·长篇批量更省钱", "unit": "积分/万字符"},
    ],
    require_confirmation=True,
    executor=_exec_batch_voice_over,
    openai_schema={
        "type": "function",
        "function": {
            "name": "batch_voice_over",
            "description": (
                "小说/剧本多角色批量配音。将文本按角色分成多段，每段指定不同音色，"
                "一次性批量合成并自动拼接为完整音频。适合小说朗读、有声书、游戏对话配音等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "segments": {
                        "type": "array",
                        "description": "按顺序排列的文本段落数组，每段指定角色和音色",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "该段文本内容"},
                                "voice_id": {"type": "string", "description": "该段使用的音色ID"},
                                "role": {"type": "string", "description": "角色名称，如'旁白'、'陈迹'、'医生'"},
                                "emotion": {
                                    "type": "string",
                                    "description": "情感: happy(开心), sad(悲伤), angry(愤怒), fearful(恐惧), disgusted(厌恶), surprised(惊讶), fluent(生动/日常对话推荐), calm(仅用于纯客观旁白)",
                                },
                                "pitch": {
                                    "type": "integer",
                                    "description": "该段音调 -12~12（可选，覆盖全局设置）",
                                },
                                "vol": {
                                    "type": "number",
                                    "description": "该段音量 0.1~10.0（可选，覆盖全局设置）",
                                },
                                "speed": {
                                    "type": "number",
                                    "description": "该段语速 0.5~2.0（可选，覆盖全局设置）",
                                },
                            },
                            "required": ["text", "voice_id", "role"],
                        },
                    },
                    "model": {
                        "type": "string",
                        "enum": ["speech-2.8-hd", "speech-2.8-turbo"],
                        "description": "语音模型：hd=高保真贵，turbo=速度快便宜约四成",
                    },
                    "speed": {"type": "number", "description": "语速 0.5~2.0，默认 1.0"},
                },
                "required": ["segments", "model"],
            },
        },
    },
))


# ===================================================================
# 8.7 upload_file (free, no confirmation)
# ===================================================================

async def _exec_upload_file(params: dict, db: AsyncSession, user: User) -> dict:
    purpose = params.get("purpose", "voice_clone")
    attachment_id = params.get("attachment_id")
    if attachment_id:
        attachment = await get_attachment(db, attachment_id, user)
        file_bytes = await read_attachment_bytes(db, attachment_id, user)
        filename = attachment.original_name
    else:
        import httpx as _httpx
        url = params["file_url"]
        async with _httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            file_bytes = resp.content
        filename = url.rsplit("/", 1)[-1].split("?")[0] or "audio.mp3"
    file_id = await voice_service.upload_file(file_bytes, filename, purpose)
    return {"file_id": file_id, "filename": filename}

_register(AgentToolDef(
    name="upload_file",
    service_type=None,
    available_models=[],
    require_confirmation=False,
    executor=_exec_upload_file,
    openai_schema={
        "type": "function",
        "function": {
            "name": "upload_file",
            "description": "上传文件（通过URL）。用于声音克隆前上传参考音频，或上传文本文件供异步语音合成使用。返回 file_id 供后续使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_url": {
                        "type": "string",
                        "description": "文件的URL地址。音频支持 mp3、m4a、wav 格式（10秒~5分钟，<20MB）",
                    },
                    "attachment_id": {
                        "type": "string",
                        "description": "已上传到 AI 助手会话的本地附件 ID。传入后优先使用本地附件",
                    },
                    "purpose": {
                        "type": "string",
                        "enum": ["voice_clone", "file_extract"],
                        "description": "文件用途: voice_clone=声音克隆参考音频, file_extract=文本文件提取。默认 voice_clone",
                    },
                },
                "required": [],
            },
        },
    },
))


# ===================================================================
# 8.8 delete_voice (requires confirmation)
# ===================================================================

async def _exec_delete_voice(params: dict, db: AsyncSession, user: User) -> dict:
    await voice_service.delete_voice(voice_id=params["voice_id"])
    return {"success": True, "voice_id": params["voice_id"]}

_register(AgentToolDef(
    name="delete_voice",
    service_type=None,
    available_models=[],
    require_confirmation=True,
    executor=_exec_delete_voice,
    openai_schema={
        "type": "function",
        "function": {
            "name": "delete_voice",
            "description": "删除自定义声音。可删除克隆或AI设计的声音，系统预置声音不可删除。",
            "parameters": {
                "type": "object",
                "properties": {
                    "voice_id": {
                        "type": "string",
                        "description": "要删除的声音ID",
                    },
                },
                "required": ["voice_id"],
            },
        },
    },
))


# ===================================================================
# 9. estimate_cost (free, no confirmation)
# ===================================================================

async def _exec_estimate_cost(params: dict, db: AsyncSession, user: User) -> dict:
    svc = params["service_type"]
    model = params.get("model")
    char_count = params.get("char_count", 0)

    # If no model specified, find all models for this service and return each price
    if not model:
        from sqlalchemy import select as _sel
        from backend.models.pricing import PricingRule
        rows = (await db.execute(
            _sel(PricingRule).where(PricingRule.service_type == svc)
        )).scalars().all()
        if rows:
            results = []
            for r in rows:
                c = await estimate_cost(db, svc, r.model, char_count)
                label = r.model or svc
                unit_label = "积分/万字符" if r.billing_unit == "per_10k_chars" else "积分"
                results.append({
                    "id": r.model or "default",
                    "name": label,
                    "model": r.model or "default",
                    "cost": c,
                    "estimated_cost": c,
                    "unit_cost": r.credits_per_use,
                    "billing_unit": r.billing_unit,
                    "unit": unit_label,
                    "char_count": char_count,
                })
            cheapest = min((r["cost"] for r in results), default=0)
            return {
                "service_type": svc,
                "char_count": char_count,
                "models": results,
                "estimated_cost": cheapest,
                "unit": "积分",
            }

    cost = await estimate_cost(db, svc, model, char_count)
    return {"service_type": svc, "model": model, "estimated_cost": cost, "unit": "积分"}

_register(AgentToolDef(
    name="estimate_cost",
    service_type=None,
    available_models=[],
    require_confirmation=False,
    executor=_exec_estimate_cost,
    openai_schema={
        "type": "function",
        "function": {
            "name": "estimate_cost",
            "description": "预估某项操作的积分消耗（免费）。在执行实际操作前可先查询费用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {
                        "type": "string",
                        "enum": ["lyrics", "music", "music_cover", "speech_sync", "speech_async", "voice_clone", "voice_design"],
                        "description": "服务类型",
                    },
                    "model": {
                        "type": "string",
                        "description": "具体模型ID（可选）",
                    },
                    "char_count": {
                        "type": "integer",
                        "description": "字符数（语音合成按字符计费时使用）",
                    },
                },
                "required": ["service_type"],
            },
        },
    },
))


# ===================================================================
# 10. query_task_status (free, no confirmation)
# ===================================================================

async def _exec_query_task_status(params: dict, db: AsyncSession, user: User) -> dict:
    return await speech_service.query_task_status(task_id=params["task_id"])

_register(AgentToolDef(
    name="query_task_status",
    service_type=None,
    available_models=[],
    require_confirmation=False,
    executor=_exec_query_task_status,
    openai_schema={
        "type": "function",
        "function": {
            "name": "query_task_status",
            "description": "查询异步语音合成任务的状态（免费）。用于长文本语音合成后跟踪进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "异步任务ID（由 long_text_to_speech 返回）",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
))


def _sync_enum_with_models() -> None:
    """Keep openai_schema.model.enum in sync with available_models.

    Single source of truth: AgentToolDef.available_models. Prevents historical drift
    where a new model was added to available_models but forgotten in the schema enum.
    """
    for tool in TOOL_REGISTRY.values():
        if not tool.available_models:
            continue
        props = (
            tool.openai_schema.get("function", {})
            .get("parameters", {})
            .get("properties", {})
        )
        model_prop = props.get("model")
        if not model_prop:
            continue
        model_prop["enum"] = [m["id"] for m in tool.available_models]


_sync_enum_with_models()
