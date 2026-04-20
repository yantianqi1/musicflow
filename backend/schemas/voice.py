from pydantic import BaseModel
from typing import Optional


class VoiceCloneRequest(BaseModel):
    file_id: int
    voice_id: str
    prompt_audio_file_id: Optional[int] = None
    prompt_text: Optional[str] = None
    text: str
    model: str = "speech-2.8-hd"


class VoiceDesignRequest(BaseModel):
    prompt: str
    preview_text: str
    voice_id: Optional[str] = None
    aigc_watermark: Optional[bool] = None


class VoiceCloneResponse(BaseModel):
    voice_id: str
    trial_audio_url: Optional[str] = None
    generation_id: str


class VoiceDesignResponse(BaseModel):
    voice_id: str
    trial_audio_url: Optional[str] = None
    generation_id: str


class VoiceItem(BaseModel):
    voice_id: str
    voice_name: Optional[str] = None
    description: Optional[str] = None
    voice_type: str
    created_time: Optional[str] = None


class VoiceListResponse(BaseModel):
    voices: list[VoiceItem]
