from backend.services.minimax_client import minimax
from backend.utils.audio import hex_to_file

import os
import uuid
import logging
import httpx as _httpx
from pathlib import Path
from backend.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# --- Silence gaps for segment transitions ---
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_SILENCE = {}

def _load_silence():
    for ms in (100, 200, 300, 500):
        p = _ASSETS_DIR / f"silence_{ms}ms.mp3"
        if p.exists():
            _SILENCE[ms] = p.read_bytes()
        else:
            logger.warning("Silence file not found: %s", p)
            _SILENCE[ms] = b""

_load_silence()

_NARRATION_ROLES = {"旁白", "叙述者", "narrator", "旁白/叙述"}


async def sync_speech(
    model: str,
    text: str,
    voice_id: str = "male-qn-qingse",
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
    emotion: str = "auto",
    sample_rate: int = 32000,
    bitrate: int = 128000,
    audio_format: str = "mp3",
    channel: int = 1,
    language_boost: str = "auto",
    aigc_watermark: bool | None = None,
    subtitle_enable: bool | None = None,
    text_normalization: bool | None = None,
    latex_read: bool | None = None,
    force_cbr: bool | None = None,
) -> dict:
    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
        },
        "audio_setting": {
            "sample_rate": sample_rate,
            "bitrate": bitrate,
            "format": audio_format,
            "channel": channel,
        },
        "language_boost": language_boost,
        "output_format": "url",
    }
    if emotion and emotion != "auto":
        payload["voice_setting"]["emotion"] = emotion
    if aigc_watermark is not None:
        payload["aigc_watermark"] = aigc_watermark
    if subtitle_enable is not None:
        payload["subtitle_enable"] = subtitle_enable
    if text_normalization is not None:
        payload["voice_setting"]["text_normalization"] = text_normalization
    if latex_read is not None:
        payload["voice_setting"]["latex_read"] = latex_read
    if force_cbr is not None:
        payload["audio_setting"]["force_cbr"] = force_cbr

    data = await minimax.post("/v1/t2a_v2", payload)
    audio = data.get("data", {}).get("audio", "")
    extra = data.get("extra_info", {})

    if audio.startswith("http"):
        audio_url = audio
    else:
        audio_url = hex_to_file(audio, audio_format)

    result = {
        "audio_url": audio_url,
        "duration_ms": extra.get("audio_length"),
    }
    subtitle_info = data.get("data", {}).get("subtitle_info")
    if subtitle_info:
        result["subtitles"] = subtitle_info
    return result


async def async_speech(
    model: str,
    text: str | None = None,
    voice_id: str = "audiobook_male_1",
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
    emotion: str = "auto",
    sample_rate: int = 32000,
    bitrate: int = 128000,
    audio_format: str = "mp3",
    channel: int = 1,
    language_boost: str = "auto",
    text_file_id: int | None = None,
) -> dict:
    payload: dict = {
        "model": model,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
        },
        "audio_setting": {
            "audio_sample_rate": sample_rate,
            "bitrate": bitrate,
            "format": audio_format,
            "channel": channel,
        },
        "language_boost": language_boost,
    }
    if text:
        payload["text"] = text
    if text_file_id is not None:
        payload["text_file_id"] = text_file_id
    if emotion and emotion != "auto":
        payload["voice_setting"]["emotion"] = emotion

    data = await minimax.post("/v1/t2a_async_v2", payload)
    return {
        "task_id": data.get("task_id", ""),
        "file_id": data.get("file_id"),
    }


async def query_task_status(task_id: str) -> dict:
    data = await minimax.get("/v1/query/t2a_async_query_v2", params={"task_id": task_id})
    return {
        "task_id": str(data.get("task_id", "")),
        "status": data.get("status", ""),
        "file_id": data.get("file_id"),
    }


async def batch_voice_over(
    segments: list[dict],
    model: str = "speech-2.8-hd",
    speed: float = 1.0,
    sample_rate: int = 32000,
    bitrate: int = 128000,
) -> dict:
    """Synthesize multiple text segments with different voices and concatenate into one audio.

    Each segment: {"text": "...", "voice_id": "...", "role": "角色名", "pitch": 0, "vol": 1.0, "speed": 1.0}
    Returns: {"audio_url": "/files/xxx.mp3", "segments_count": N, "total_chars": N, "details": [...]}
    """
    import asyncio

    # --- Build tasks for all segments ---
    tasks = []      # (index, payload, role, chars, voice_id)
    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        voice_id = seg.get("voice_id", "male-qn-qingse")
        role = seg.get("role", f"segment_{i}")
        emotion = seg.get("emotion")
        seg_speed = seg.get("speed", speed)
        seg_vol = seg.get("vol", 1.0)
        seg_pitch = seg.get("pitch", 0)

        payload = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": seg_speed,
                "vol": seg_vol,
                "pitch": seg_pitch,
            },
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "format": "mp3",
                "channel": 2,
            },
            "language_boost": "auto",
            "output_format": "url",
        }
        if emotion and emotion != "auto":
            payload["voice_setting"]["emotion"] = emotion

        tasks.append((i, payload, role, len(text), voice_id))

    if not tasks:
        raise ValueError("没有有效的文本段落可合成")

    # --- Concurrent synthesis with rate-limit-aware throttling ---
    sem = asyncio.Semaphore(3)          # max 3 parallel requests
    _REQUEST_INTERVAL = 1.5             # seconds between launching requests
    _SEGMENT_MAX_RETRIES = 3            # per-segment retries (on top of minimax_client retries)
    _SEGMENT_RETRY_DELAYS = [15, 30, 60]  # seconds – generous for RPM recovery

    async def _synthesize_one(payload: dict) -> bytes:
        async with sem:
            data = await minimax.post("/v1/t2a_v2", payload)
            audio_ref = data.get("data", {}).get("audio", "")
            if audio_ref.startswith("http"):
                async with _httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(audio_ref)
                    resp.raise_for_status()
                    return resp.content
            else:
                return bytes.fromhex(audio_ref)

    async def _synthesize_with_retry(idx: int, payload: dict, role: str) -> bytes:
        """Wrap _synthesize_one with segment-level retries."""
        last_err = None
        for attempt in range(_SEGMENT_MAX_RETRIES):
            try:
                return await _synthesize_one(payload)
            except Exception as e:
                last_err = e
                if attempt < _SEGMENT_MAX_RETRIES - 1:
                    delay = _SEGMENT_RETRY_DELAYS[attempt]
                    logger.warning(
                        "段落 %d(%s) 第%d次合成失败, %d秒后重试: %s",
                        idx + 1, role, attempt + 1, delay, e,
                    )
                    await asyncio.sleep(delay)
        raise RuntimeError(f"段落 {idx+1}({role}) 经{_SEGMENT_MAX_RETRIES}次重试后仍失败: {last_err}")

    # Stagger launches to avoid RPM burst
    async def _staggered_launch():
        coros = []
        for i, (idx, payload, role, _, _) in enumerate(tasks):
            if i > 0:
                await asyncio.sleep(_REQUEST_INTERVAL)
            coros.append(asyncio.create_task(_synthesize_with_retry(idx, payload, role)))
        return await asyncio.gather(*coros, return_exceptions=True)

    results = await _staggered_launch()

    # --- Assemble in original order with silence gaps ---
    audio_chunks: list[bytes] = []
    details = []
    for (idx, payload, role, chars, voice_id), result in zip(tasks, results):
        if isinstance(result, Exception):
            raise RuntimeError(str(result))
        audio_chunks.append(result)
        details.append({"role": role, "chars": chars, "voice_id": voice_id})

    # Concatenate with role-aware silence gaps
    parts: list[bytes] = []
    for i, chunk in enumerate(audio_chunks):
        if i > 0 and _SILENCE:
            prev_role = details[i - 1]["role"]
            curr_role = details[i]["role"]
            prev_is_narr = prev_role in _NARRATION_ROLES
            curr_is_narr = curr_role in _NARRATION_ROLES
            if prev_is_narr != curr_is_narr:
                parts.append(_SILENCE.get(300, b""))   # narration <-> dialogue
            elif prev_role != curr_role:
                parts.append(_SILENCE.get(200, b""))   # different characters
            else:
                parts.append(_SILENCE.get(100, b""))   # same character continues
        parts.append(chunk)

    combined = b"".join(parts)
    filename = f"novel_{uuid.uuid4().hex[:10]}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(combined)

    total_chars = sum(d["chars"] for d in details)

    return {
        "audio_url": f"/files/{filename}",
        "segments_count": len(details),
        "total_chars": total_chars,
        "details": details,
    }
