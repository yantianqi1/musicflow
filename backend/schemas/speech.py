from pydantic import BaseModel
from typing import Literal, Optional


class VoiceSetting(BaseModel):
    voice_id: str = "male-qn-qingse"
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    emotion: str = "auto"


class SpeechAudioSetting(BaseModel):
    sample_rate: int = 32000
    bitrate: int = 128000
    format: Literal["mp3", "wav", "pcm", "flac"] = "mp3"
    channel: int = 1
    force_cbr: Optional[bool] = None


class SyncSpeechRequest(BaseModel):
    model: str = "speech-2.8-hd"
    text: str
    voice_setting: VoiceSetting = VoiceSetting()
    audio_setting: SpeechAudioSetting = SpeechAudioSetting()
    language_boost: str = "auto"
    aigc_watermark: Optional[bool] = None
    subtitle_enable: Optional[bool] = None
    text_normalization: Optional[bool] = None
    latex_read: Optional[bool] = None


class SyncSpeechResponse(BaseModel):
    audio_url: str
    duration_ms: Optional[int] = None
    generation_id: str
    subtitle_info: Optional[dict] = None


class AsyncSpeechRequest(BaseModel):
    model: str = "speech-2.8-hd"
    text: Optional[str] = None
    text_file_id: Optional[int] = None
    voice_setting: VoiceSetting = VoiceSetting()
    audio_setting: SpeechAudioSetting = SpeechAudioSetting()
    language_boost: str = "auto"


class AsyncSpeechResponse(BaseModel):
    task_id: str
    generation_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    file_id: Optional[int] = None
