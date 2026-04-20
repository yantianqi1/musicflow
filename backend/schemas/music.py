from pydantic import BaseModel
from typing import Literal, Optional


class AudioSetting(BaseModel):
    sample_rate: int = 44100
    bitrate: int = 256000
    format: Literal["mp3", "wav", "pcm"] = "mp3"


class LyricsRequest(BaseModel):
    mode: str = "write_full_song"
    prompt: str = ""
    lyrics: Optional[str] = None
    title: Optional[str] = None


class LyricsResponse(BaseModel):
    song_title: str
    style_tags: str
    lyrics: str


class MusicGenerateRequest(BaseModel):
    model: str = "music-2.6"
    prompt: str = ""
    lyrics: Optional[str] = None
    audio_setting: AudioSetting = AudioSetting()
    is_instrumental: bool = False
    lyrics_optimizer: bool = False
    aigc_watermark: Optional[bool] = None
    stream: Optional[bool] = None


class CoverRequest(BaseModel):
    model: str = "music-cover"
    prompt: str
    audio_url: Optional[str] = None
    audio_base64: Optional[str] = None
    lyrics: Optional[str] = None
    audio_setting: AudioSetting = AudioSetting()
    aigc_watermark: Optional[bool] = None


class MusicResponse(BaseModel):
    audio_url: str
    duration_ms: Optional[int] = None
    file_size: Optional[int] = None
    generation_id: str
