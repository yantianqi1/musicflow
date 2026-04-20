from backend.services.minimax_client import minimax
from backend.utils.audio import hex_to_file


async def upload_file(file_bytes: bytes, filename: str, purpose: str) -> int:
    data = await minimax.upload_file(file_bytes, filename, purpose)
    return data.get("file", {}).get("file_id")


async def clone_voice(
    file_id: int,
    voice_id: str,
    text: str,
    model: str = "speech-2.8-hd",
    prompt_audio_file_id: int | None = None,
    prompt_text: str | None = None,
) -> dict:
    payload: dict = {
        "file_id": file_id,
        "voice_id": voice_id,
        "text": text,
        "model": model,
    }
    if prompt_audio_file_id or prompt_text:
        clone_prompt: dict = {}
        if prompt_audio_file_id:
            clone_prompt["prompt_audio"] = prompt_audio_file_id
        if prompt_text:
            clone_prompt["prompt_text"] = prompt_text
        payload["clone_prompt"] = clone_prompt

    data = await minimax.post("/v1/voice_clone", payload)
    trial_audio = data.get("demo_audio") or data.get("trial_audio", "")
    trial_url = None
    if trial_audio and not trial_audio.startswith("http"):
        trial_url = hex_to_file(trial_audio, "mp3")
    elif trial_audio:
        trial_url = trial_audio

    return {"voice_id": voice_id, "trial_audio_url": trial_url}


async def design_voice(prompt: str, preview_text: str, voice_id: str | None = None,
                       aigc_watermark: bool | None = None) -> dict:
    payload: dict = {"prompt": prompt, "preview_text": preview_text}
    if voice_id:
        payload["voice_id"] = voice_id
    if aigc_watermark is not None:
        payload["aigc_watermark"] = aigc_watermark

    data = await minimax.post("/v1/voice_design", payload)
    result_voice_id = data.get("voice_id", "")
    trial_audio = data.get("trial_audio", "")
    trial_url = None
    if trial_audio and not trial_audio.startswith("http"):
        trial_url = hex_to_file(trial_audio, "mp3")
    elif trial_audio:
        trial_url = trial_audio

    return {"voice_id": result_voice_id, "trial_audio_url": trial_url}


async def list_voices(voice_type: str = "all") -> dict:
    data = await minimax.post("/v1/get_voice", {"voice_type": voice_type})
    voices = []
    for v in data.get("system_voice", []):
        voices.append({
            "voice_id": v["voice_id"],
            "voice_name": v.get("voice_name"),
            "description": v["description"][0] if v.get("description") else None,
            "voice_type": "system",
            "created_time": v.get("created_time"),
        })
    for v in data.get("voice_cloning", []):
        voices.append({
            "voice_id": v["voice_id"],
            "voice_name": None,
            "description": v["description"][0] if v.get("description") else None,
            "voice_type": "cloned",
            "created_time": v.get("created_time"),
        })
    for v in data.get("voice_generation", []):
        voices.append({
            "voice_id": v["voice_id"],
            "voice_name": None,
            "description": v["description"][0] if v.get("description") else None,
            "voice_type": "designed",
            "created_time": v.get("created_time"),
        })
    return {"voices": voices}


async def delete_voice(voice_id: str) -> dict:
    data = await minimax.post("/v1/delete_voice", {"voice_id": voice_id})
    return {"success": True}
