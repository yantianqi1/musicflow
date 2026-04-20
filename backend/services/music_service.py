from backend.services.minimax_client import minimax
from backend.utils.audio import hex_to_file


# ---------------------------------------------------------------------------
# Duration → lyrics structure mapping
# ---------------------------------------------------------------------------

DURATION_LYRICS_GUIDE = {
    "short": (
        "请生成一段简短的歌词，只包含1个段落（仅Verse或仅Chorus），总共4-6行，"
        "适合约20-40秒的短音乐。"
    ),
    "medium": (
        "请生成中等长度的歌词，包含[Verse]+[Chorus]结构，总共8-14行，"
        "适合约1-2分钟的音乐。"
    ),
    "standard": (
        "请生成标准长度的完整歌词，包含[Verse]+[Chorus]+[Verse]+[Chorus]+[Bridge]+[Outro]结构，"
        "总共16-24行，适合约2-3分钟的歌曲。"
    ),
    "long": (
        "请生成较长的完整歌词，包含[Intro]+[Verse]+[Pre Chorus]+[Chorus]+[Verse]+[Chorus]+"
        "[Bridge]+[Chorus]+[Outro]等丰富结构，总共24-36行，适合约3-4分钟的歌曲。"
    ),
}

DURATION_INSTRUMENTAL_HINT = {
    "short": "，曲目简短约20-40秒",
    "medium": "，曲目中等长度约1-2分钟",
    "standard": "，曲目标准长度约2-3分钟",
    "long": "，曲目较长约3-4分钟",
}


async def generate_lyrics(prompt: str, mode: str = "write_full_song", lyrics: str | None = None,
                          title: str | None = None, target_duration: str | None = None) -> dict:
    payload: dict = {"mode": mode}
    # Inject duration guidance into prompt
    effective_prompt = prompt
    if target_duration and target_duration in DURATION_LYRICS_GUIDE:
        effective_prompt = f"{DURATION_LYRICS_GUIDE[target_duration]}主题：{prompt}"
    if effective_prompt:
        payload["prompt"] = effective_prompt
    if lyrics:
        payload["lyrics"] = lyrics
    if title:
        payload["title"] = title
    data = await minimax.post("/v1/lyrics_generation", payload)
    return {
        "song_title": data.get("song_title", ""),
        "style_tags": data.get("style_tags", ""),
        "lyrics": data.get("lyrics", ""),
    }


async def generate_music(
    model: str,
    prompt: str = "",
    lyrics: str | None = None,
    sample_rate: int = 44100,
    bitrate: int = 256000,
    audio_format: str = "mp3",
    is_instrumental: bool = False,
    lyrics_optimizer: bool = False,
    target_duration: str | None = None,
    aigc_watermark: bool | None = None,
    stream: bool | None = None,
) -> dict:
    # For instrumental, append duration hint to prompt
    effective_prompt = prompt
    if is_instrumental and target_duration and target_duration in DURATION_INSTRUMENTAL_HINT:
        effective_prompt = prompt + DURATION_INSTRUMENTAL_HINT[target_duration]

    payload: dict = {
        "model": model,
        "audio_setting": {"sample_rate": sample_rate, "bitrate": bitrate, "format": audio_format},
        "output_format": "url",
    }
    if effective_prompt:
        payload["prompt"] = effective_prompt
    if lyrics:
        payload["lyrics"] = lyrics
    if is_instrumental:
        payload["is_instrumental"] = True
    if lyrics_optimizer:
        payload["lyrics_optimizer"] = True
    if aigc_watermark is not None:
        payload["aigc_watermark"] = aigc_watermark
    if stream is not None:
        payload["stream"] = stream

    data = await minimax.post("/v1/music_generation", payload)
    audio = data.get("data", {}).get("audio", "")
    extra = data.get("extra_info", {})

    # 如果返回的是 URL（output_format=url），直接用；否则 hex 转文件
    if audio.startswith("http"):
        audio_url = audio
    else:
        audio_url = hex_to_file(audio, audio_format)

    return {
        "audio_url": audio_url,
        "duration_ms": extra.get("music_duration"),
        "file_size": extra.get("music_size"),
    }


async def generate_cover(
    model: str,
    prompt: str,
    audio_url: str | None = None,
    audio_base64: str | None = None,
    lyrics: str | None = None,
    sample_rate: int = 44100,
    bitrate: int = 256000,
    audio_format: str = "mp3",
    aigc_watermark: bool | None = None,
) -> dict:
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "audio_setting": {"sample_rate": sample_rate, "bitrate": bitrate, "format": audio_format},
        "output_format": "url",
    }
    if audio_url:
        payload["audio_url"] = audio_url
    if audio_base64:
        payload["audio_base64"] = audio_base64
    if lyrics:
        payload["lyrics"] = lyrics
    if aigc_watermark is not None:
        payload["aigc_watermark"] = aigc_watermark

    data = await minimax.post("/v1/music_generation", payload)
    audio = data.get("data", {}).get("audio", "")
    extra = data.get("extra_info", {})

    if audio.startswith("http"):
        result_url = audio
    else:
        result_url = hex_to_file(audio, audio_format)

    return {
        "audio_url": result_url,
        "duration_ms": extra.get("music_duration"),
        "file_size": extra.get("music_size"),
    }
